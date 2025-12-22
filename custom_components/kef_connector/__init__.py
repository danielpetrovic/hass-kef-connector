"""The KEF Connector integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol

from .pykefcontrol.kef_connector import KefAsyncConnector

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.storage import Store

from .const import (
    CONF_OFFLINE_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SPEAKER_MODEL,
    DEFAULT_OFFLINE_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import KefCoordinator

_LOGGER = logging.getLogger(__name__)

# Storage version for EQ profiles
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.profiles"

# Service schemas
SERVICE_SAVE_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("name"): str,
        vol.Optional("description", default=""): str,
    }
)

SERVICE_LOAD_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("name"): str,
    }
)

SERVICE_DELETE_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("name"): str,
    }
)

SERVICE_LIST_PROFILES_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): str,
    }
)

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.UPDATE,
]


class KefHassAsyncConnector(KefAsyncConnector):
    """KefAsyncConnector with Home Assistant session management."""

    def __init__(
        self,
        host: str,
        session=None,
        hass: HomeAssistant | None = None,
    ) -> None:
        """Initialize the KefAsyncConnector."""
        super().__init__(host, session=session)
        self.hass = hass

    async def resurect_session(self):
        """Resurect the session if it is closed."""
        if self._session is None:
            self._session = aiohttp_client.async_get_clientsession(self.hass)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the KEF Connector integration."""
    # Register services (only once per integration)
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KEF Connector from a config entry."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    speaker_model = entry.data.get(CONF_SPEAKER_MODEL, "LSX2")

    # Get options with defaults
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    offline_retry_interval = entry.options.get(
        CONF_OFFLINE_RETRY_INTERVAL, DEFAULT_OFFLINE_RETRY_INTERVAL
    )

    # Create aiohttp session
    session = aiohttp_client.async_get_clientsession(hass)

    # Create KEF speaker connector
    speaker = KefHassAsyncConnector(host, session=session, hass=hass)

    # Create coordinator
    coordinator = KefCoordinator(
        hass,
        speaker,
        name,
        scan_interval,
        offline_retry_interval,
        speaker_model,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Get coordinator
    coordinator: KefCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Update intervals
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    offline_retry_interval = entry.options.get(
        CONF_OFFLINE_RETRY_INTERVAL, DEFAULT_OFFLINE_RETRY_INTERVAL
    )
    coordinator.update_intervals(scan_interval, offline_retry_interval)

    # Request coordinator refresh with new interval
    await coordinator.async_request_refresh()


def _get_coordinator_from_device_id(
    hass: HomeAssistant, device_id: str
) -> KefCoordinator | None:
    """Get coordinator from device ID."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if not device:
        return None

    # Find the config entry for this device
    for entry_id in device.config_entries:
        if entry_id in hass.data.get(DOMAIN, {}):
            return hass.data[DOMAIN][entry_id]
    return None


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for KEF Connector."""

    async def async_save_eq_profile(call: ServiceCall) -> None:
        """Save current EQ settings to a profile."""
        device_id = call.data["device_id"]
        profile_name = call.data["name"]
        description = call.data.get("description", "")

        coordinator = _get_coordinator_from_device_id(hass, device_id)
        if not coordinator:
            _LOGGER.error("Device not found: %s", device_id)
            return

        # Get current EQ profile from speaker
        eq_profile = await coordinator.speaker.get_eq_profile()
        if not eq_profile:
            _LOGGER.error("Could not get EQ profile from speaker")
            return

        # Get MAC address for storage key
        mac_address = await coordinator.speaker.mac_address
        mac_formatted = format_mac(mac_address).replace(":", "")

        # Create storage for this speaker
        store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{mac_formatted}")
        data = await store.async_load() or {"profiles": {}}

        # Save profile with metadata
        data["profiles"][profile_name] = {
            "eq_profile": eq_profile,
            "description": description,
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
        }

        await store.async_save(data)
        _LOGGER.info("Saved EQ profile '%s' for speaker %s", profile_name, mac_address)

    async def async_load_eq_profile(call: ServiceCall) -> None:
        """Load and apply a saved EQ profile."""
        device_id = call.data["device_id"]
        profile_name = call.data["name"]

        coordinator = _get_coordinator_from_device_id(hass, device_id)
        if not coordinator:
            _LOGGER.error("Device not found: %s", device_id)
            return

        # Get MAC address for storage key
        mac_address = await coordinator.speaker.mac_address
        mac_formatted = format_mac(mac_address).replace(":", "")

        # Load profiles from storage
        store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{mac_formatted}")
        data = await store.async_load()

        if not data or profile_name not in data.get("profiles", {}):
            _LOGGER.error("Profile '%s' not found", profile_name)
            return

        # Apply the EQ profile to speaker
        eq_profile = data["profiles"][profile_name]["eq_profile"]
        await coordinator.speaker.set_eq_profile(eq_profile)

        # Refresh coordinator to update entities
        await coordinator.async_request_refresh()
        _LOGGER.info("Loaded EQ profile '%s' for speaker %s", profile_name, mac_address)

    async def async_delete_eq_profile(call: ServiceCall) -> None:
        """Delete a saved EQ profile."""
        device_id = call.data["device_id"]
        profile_name = call.data["name"]

        coordinator = _get_coordinator_from_device_id(hass, device_id)
        if not coordinator:
            _LOGGER.error("Device not found: %s", device_id)
            return

        # Get MAC address for storage key
        mac_address = await coordinator.speaker.mac_address
        mac_formatted = format_mac(mac_address).replace(":", "")

        # Load profiles from storage
        store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{mac_formatted}")
        data = await store.async_load()

        if not data or profile_name not in data.get("profiles", {}):
            _LOGGER.error("Profile '%s' not found", profile_name)
            return

        # Delete the profile
        del data["profiles"][profile_name]
        await store.async_save(data)
        _LOGGER.info("Deleted EQ profile '%s' for speaker %s", profile_name, mac_address)

    async def async_list_eq_profiles(call: ServiceCall) -> ServiceResponse:
        """List all saved EQ profiles for a speaker."""
        device_id = call.data["device_id"]

        coordinator = _get_coordinator_from_device_id(hass, device_id)
        if not coordinator:
            _LOGGER.error("Device not found: %s", device_id)
            return {"profiles": []}

        # Get MAC address for storage key
        mac_address = await coordinator.speaker.mac_address
        mac_formatted = format_mac(mac_address).replace(":", "")

        # Load profiles from storage
        store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{mac_formatted}")
        data = await store.async_load()

        if not data:
            return {"profiles": []}

        profiles = []
        for name, profile_data in data.get("profiles", {}).items():
            profiles.append({
                "name": name,
                "description": profile_data.get("description", ""),
                "created": profile_data.get("created", ""),
                "modified": profile_data.get("modified", ""),
            })

        return {"profiles": profiles}

    # Register services
    hass.services.async_register(
        DOMAIN,
        "save_eq_profile",
        async_save_eq_profile,
        schema=SERVICE_SAVE_PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "load_eq_profile",
        async_load_eq_profile,
        schema=SERVICE_LOAD_PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "delete_eq_profile",
        async_delete_eq_profile,
        schema=SERVICE_DELETE_PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "list_eq_profiles",
        async_list_eq_profiles,
        schema=SERVICE_LIST_PROFILES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
