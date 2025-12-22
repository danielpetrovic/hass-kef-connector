"""Update platform for KEF Connector integration."""
from __future__ import annotations

import logging
import re

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODEL_NAMES
from .coordinator import KefCoordinator
from .entity import KefBaseEntity
from .pykefcontrol.kef_connector import get_kef_firmware_releases

_LOGGER = logging.getLogger(__name__)


def _parse_firmware_version(version_str: str) -> tuple[int, int, int] | None:
    """Parse firmware version string to comparable tuple.

    Handles formats like:
    - "V26120" -> (2, 6, 120)
    - "V25110" -> (2, 5, 110)
    - "V1670" -> (1, 6, 70)
    - "2.6" -> (2, 6, 0)
    """
    if not version_str:
        return None

    # Handle "V26120" format (API format)
    if version_str.startswith("V"):
        digits = version_str[1:]
        if len(digits) >= 4:
            # V26120 -> major=2, minor=6, patch=120
            major = int(digits[0])
            minor = int(digits[1])
            patch = int(digits[2:])
            return (major, minor, patch)

    # Handle "2.6" format (release notes format)
    match = re.match(r"(\d+)\.(\d+)", version_str)
    if match:
        return (int(match.group(1)), int(match.group(2)), 0)

    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF Connector update entity from config entry."""
    coordinator: KefCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([KefFirmwareUpdate(coordinator, entry)])


class KefFirmwareUpdate(KefBaseEntity, UpdateEntity):
    """Representation of KEF firmware update."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES

    def __init__(
        self,
        coordinator: KefCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator, entry, "firmware_update")
        self._attr_name = "Firmware"
        self._latest_version: str | None = None
        self._release_notes: str | None = None
        self._checked_for_updates = False
        self._update_in_progress: bool | int = False

    @property
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        if not self.coordinator.last_update_success:
            return None
        return self.coordinator.data.get("firmware_version")

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        if self._latest_version:
            return self._latest_version
        # Return installed version if we haven't checked yet
        return self.installed_version

    @property
    def release_summary(self) -> str | None:
        """Return the release notes summary."""
        return self._release_notes

    def release_notes(self) -> str | None:
        """Return full release notes."""
        return self._release_notes

    @property
    def in_progress(self) -> bool | int:
        """Return if the update is in progress.

        Returns True/False or an integer representing the progress percentage.
        """
        return self._update_in_progress

    async def async_install(
        self, version: str | None, backup: bool, **kwargs
    ) -> None:
        """Install the firmware update.

        The firmware update flow is:
        1. firmwareupdate:checkForUpdate (activate) - Check for available update
        2. firmwareupdate:downloadNewUpdate (activate) - Start download and install
        3. firmwareupdate:updateStatus (value) - Monitor progress
        4. kef:fwupgrade/info (value) - Get detailed upgrade info

        The speaker will download the update, reboot, and apply it automatically.
        During this time the speaker will be unreachable (typically 2-5 minutes).
        """
        import asyncio

        _LOGGER.info("Starting firmware update for KEF speaker")
        self._update_in_progress = True
        self.async_write_ha_state()

        speaker = self.coordinator.speaker

        # Step 1: Check for updates (required before download)
        try:
            # First get update status to see if update is available
            status_result = await speaker.get_request("firmwareupdate:updateStatus", roles="value")
            _LOGGER.info("Update status: %s", status_result)

            if not status_result:
                _LOGGER.warning("Could not get firmware update status")
                self._update_in_progress = False
                self.async_write_ha_state()
                return

            # Check if update is available
            fw_status = status_result[0].get("firmwareUpdateStatus", {}) if status_result else {}
            state = fw_status.get("state", "idle")

            if state != "newUpdateAvailable":
                _LOGGER.info("No firmware update available (state: %s)", state)
                self._update_in_progress = False
                self.async_write_ha_state()
                return

            firmware_url = fw_status.get("imageDescription", {}).get("url")
            firmware_version = fw_status.get("imageDescription", {}).get("version")
            _LOGGER.info("Firmware available: version=%s, url=%s", firmware_version, firmware_url)

        except Exception as e:
            _LOGGER.error("Firmware check failed: %s", e)
            self._update_in_progress = False
            self.async_write_ha_state()
            return

        # Step 2: Trigger firmware download and install
        try:
            _LOGGER.info("Triggering firmware download via firmwareupdate:downloadNewUpdate")
            result = await speaker.set_request(
                "firmwareupdate:downloadNewUpdate",
                roles="activate",
                value='{"type":"bool_","bool_":true}'
            )
            _LOGGER.info("Download trigger result: %s", result)

            if isinstance(result, dict) and 'error' in result:
                _LOGGER.error("Failed to trigger firmware download: %s", result.get('error'))
                self._update_in_progress = False
                self.async_write_ha_state()
                return

            _LOGGER.info(
                "Firmware update initiated. Speaker will download, reboot, and apply update. "
                "This typically takes 2-5 minutes. Speaker will be unavailable during this time."
            )

        except Exception as e:
            _LOGGER.error("Failed to trigger firmware download: %s", e)
            self._update_in_progress = False
            self.async_write_ha_state()
            return

        # Step 3: Wait for update to complete (with timeout)
        # The speaker will be unreachable during the update
        max_wait_seconds = 300  # 5 minutes max
        poll_interval = 10
        waited = 0

        while waited < max_wait_seconds:
            await asyncio.sleep(poll_interval)
            waited += poll_interval

            try:
                status = await speaker.get_request("firmwareupdate:updateStatus", roles="value")
                if status:
                    fw_status = status[0].get("firmwareUpdateStatus", {})
                    state = fw_status.get("state", "unknown")
                    progress = fw_status.get("downloadProgress", 0)

                    _LOGGER.debug("Update status: state=%s, progress=%s%%", state, progress)

                    if state == "idle":
                        # Update complete
                        _LOGGER.info("Firmware update completed successfully!")
                        self._update_in_progress = False
                        # Reset latest version to trigger re-check
                        self._latest_version = None
                        break
                    elif state in ("downloading", "validating", "updating"):
                        # Still in progress
                        self._update_in_progress = progress if progress > 0 else True
                        self.async_write_ha_state()
                    elif state == "newUpdateAvailable":
                        # Update hasn't started yet
                        pass

            except Exception:
                # Speaker likely rebooting - this is expected
                _LOGGER.debug("Speaker unreachable during update (waited %ds)", waited)
                self._update_in_progress = True

        self._update_in_progress = False
        self.async_write_ha_state()

        # Refresh coordinator to get new firmware version
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        # Check for updates when entity is first added
        await self._async_check_for_updates()

    async def _async_check_for_updates(self) -> None:
        """Check for available firmware updates."""
        try:
            # Get speaker model for filtering releases
            speaker_model = self.speaker_model
            model_display = MODEL_NAMES.get(speaker_model, speaker_model)

            # Fetch firmware releases from KEF
            releases_dict = await self.hass.async_add_executor_job(
                get_kef_firmware_releases, model_display
            )

            if releases_dict:
                # releases_dict is {model_name: [releases]}
                for model_name, releases in releases_dict.items():
                    if releases:
                        latest = releases[0]
                        latest_version_str = latest.get("version")
                        notes = latest.get("notes", [])

                        # Convert release notes version to API format for comparison
                        # "2.6" from release notes, compare with "V26120" from API
                        installed = self.installed_version
                        installed_tuple = _parse_firmware_version(installed)
                        latest_tuple = _parse_firmware_version(latest_version_str)

                        _LOGGER.debug(
                            "Firmware check: installed=%s (%s), latest=%s (%s)",
                            installed, installed_tuple, latest_version_str, latest_tuple
                        )

                        if installed_tuple and latest_tuple:
                            # Compare major.minor only (ignore patch for release notes comparison)
                            if (latest_tuple[0], latest_tuple[1]) > (installed_tuple[0], installed_tuple[1]):
                                # Newer version available - show in API format
                                self._latest_version = f"V{latest_tuple[0]}{latest_tuple[1]}000"
                                if isinstance(notes, list):
                                    self._release_notes = "\n".join(f"- {note}" for note in notes)
                                else:
                                    self._release_notes = str(notes)
                                _LOGGER.info(
                                    "Firmware update available: %s -> %s",
                                    installed, self._latest_version
                                )
                            else:
                                # Up to date
                                self._latest_version = installed
                                self._release_notes = None
                        break

            self._checked_for_updates = True

        except Exception as err:
            _LOGGER.debug("Could not fetch KEF firmware releases: %s", err)
