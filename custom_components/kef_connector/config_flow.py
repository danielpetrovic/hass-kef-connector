"""Config flow for KEF Connector integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .pykefcontrol.kef_connector import KefAsyncConnector
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, selector
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.storage import Store

from .const import (
    CONF_OFFLINE_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SPEAKER_MODEL,
    DEFAULT_OFFLINE_RETRY_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    KEF_ZEROCONF_PREFIXES,
    MAX_OFFLINE_RETRY_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_OFFLINE_RETRY_INTERVAL,
    MIN_SCAN_INTERVAL,
)

# Storage constants for EQ profiles
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.profiles"

_LOGGER = logging.getLogger(__name__)


def parse_model_from_discovery(discovery_info: zeroconf.ZeroconfServiceInfo) -> str:
    """Parse KEF speaker model from zeroconf discovery info.

    Google Cast names typically contain the model name.
    Examples: "KEF LSX2", "KEF LSX2LT", "KEF LS60", etc.
    """
    # Check the service name first (this is where Google Cast puts the device name)
    name = discovery_info.name.upper()

    # Check for known models in order of specificity (most specific first)
    if "LSX2LT" in name or "LSX II LT" in name or "LSX-II-LT" in name:
        return "LSX2LT"
    elif "LSX2" in name or "LSX II" in name or "LSX-II" in name:
        return "LSX2"
    elif "LS50W2" in name or "LS50 WIRELESS II" in name or "LS50-WIRELESS-II" in name:
        return "LS50W2"
    elif "LS60" in name:
        return "LS60"
    elif "XIO" in name:
        return "XIO"

    # Also check properties dict in case it's there
    properties = discovery_info.properties
    if properties:
        # Check for model in common property keys
        for key in ["md", "model", "device_model"]:
            if key in properties:
                model_value = properties[key].upper()
                if "LSX2LT" in model_value:
                    return "LSX2LT"
                elif "LSX2" in model_value:
                    return "LSX2"
                elif "LS50W2" in model_value:
                    return "LS50W2"
                elif "LS60" in model_value:
                    return "LS60"
                elif "XIO" in model_value:
                    return "XIO"

    # Default to LSX2 if we can't detect
    _LOGGER.debug(
        "Could not detect KEF model from discovery info (name=%s), defaulting to LSX2",
        discovery_info.name
    )
    return "LSX2"


def is_kef_speaker(discovery_info: zeroconf.ZeroconfServiceInfo) -> bool:
    """Check if discovered device is a KEF speaker based on zeroconf name.

    KEF speakers advertise with specific Google Cast name patterns.
    Returns True if the device appears to be a KEF speaker.
    """
    name_upper = discovery_info.name.upper()
    return any(name_upper.startswith(prefix) for prefix in KEF_ZEROCONF_PREFIXES)


async def validate_connection(
    hass: HomeAssistant, host: str
) -> dict[str, Any]:
    """Validate the connection to a KEF speaker.

    Returns dict with:
        - mac_address: for unique_id
        - speaker_name: for friendly name
        - speaker_model: for device info and source list
    """
    session = aiohttp_client.async_get_clientsession(hass)
    connector = KefAsyncConnector(host, session=session)

    try:
        # Get speaker information
        mac_address = await connector.mac_address
        speaker_name = await connector.speaker_name

        # Validate we got valid data
        if not mac_address or not speaker_name:
            raise ValueError("Unable to retrieve speaker information")

        # Note: speaker_model is not available from the API
        # We'll default to "LSX2" which is the most common model
        return {
            "mac_address": format_mac(mac_address),
            "speaker_name": speaker_name,
            "speaker_model": "LSX2",
        }
    except Exception as err:
        _LOGGER.error("Error connecting to KEF speaker at %s: %s", host, err)
        raise


class KefConnectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KEF Connector."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None
        self._detected_model: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - manual IP entry."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            try:
                info = await validate_connection(self.hass, host)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                # Set unique ID to prevent duplicates
                await self.async_set_unique_id(info["mac_address"])
                self._abort_if_unique_id_configured()

                # Get user-selected model and options
                speaker_model = user_input.get(CONF_SPEAKER_MODEL, "LSX2").upper()
                options = {
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_OFFLINE_RETRY_INTERVAL: user_input.get(
                        CONF_OFFLINE_RETRY_INTERVAL, DEFAULT_OFFLINE_RETRY_INTERVAL
                    ),
                }

                return self.async_create_entry(
                    title=info["speaker_name"],
                    data={
                        CONF_HOST: host,
                        CONF_NAME: info["speaker_name"],
                        CONF_SPEAKER_MODEL: speaker_model,
                    },
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_SPEAKER_MODEL, default="LSX2"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["LSX2", "LSX2LT", "LS50W2", "LS60", "XIO"],
                        translation_key="speaker_model",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL,
                ): vol.All(vol.Coerce(int), vol.Range(
                    min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL
                )),
                vol.Required(
                    CONF_OFFLINE_RETRY_INTERVAL,
                    default=DEFAULT_OFFLINE_RETRY_INTERVAL,
                ): vol.All(vol.Coerce(int), vol.Range(
                    min=MIN_OFFLINE_RETRY_INTERVAL, max=MAX_OFFLINE_RETRY_INTERVAL
                )),
            }),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host

        # Filter: Only process KEF speakers
        if not is_kef_speaker(discovery_info):
            _LOGGER.debug(
                "Ignoring non-KEF Google Cast device '%s' at %s",
                discovery_info.name,
                host
            )
            return self.async_abort(reason="not_kef_device")

        # Try to get speaker info
        try:
            info = await validate_connection(self.hass, host)
        except Exception:
            return self.async_abort(reason="cannot_connect")

        # Set unique ID and abort if already configured
        await self.async_set_unique_id(info["mac_address"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Parse model from discovery info (Google Cast name)
        self._detected_model = parse_model_from_discovery(discovery_info)
        _LOGGER.info(
            "Detected KEF model '%s' for speaker '%s' from zeroconf discovery",
            self._detected_model,
            info["speaker_name"]
        )

        # Store discovered info for confirmation step
        self._discovered_host = host
        self._discovered_name = info["speaker_name"]

        # Set suggested name in context for the UI
        self.context["title_placeholders"] = {
            "name": info["speaker_name"],
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            # User confirmed, get full speaker info
            try:
                info = await validate_connection(self.hass, self._discovered_host)
            except Exception:
                return self.async_abort(reason="cannot_connect")

            # Use the user-selected model
            speaker_model = user_input.get(CONF_SPEAKER_MODEL, "LSX2").upper()

            # Extract options for initial setup
            options = {
                CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                CONF_OFFLINE_RETRY_INTERVAL: user_input.get(
                    CONF_OFFLINE_RETRY_INTERVAL, DEFAULT_OFFLINE_RETRY_INTERVAL
                ),
            }

            return self.async_create_entry(
                title=info["speaker_name"],
                data={
                    CONF_HOST: self._discovered_host,
                    CONF_NAME: info["speaker_name"],
                    CONF_SPEAKER_MODEL: speaker_model,
                },
                options=options,
            )

        # Show form with speaker model selection (using detected model as default)
        detected_model = self._detected_model or "LSX2"
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_SPEAKER_MODEL, default=detected_model): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["LSX2", "LSX2LT", "LS50W2", "LS60", "XIO"],
                        translation_key="speaker_model",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL,
                ): vol.All(vol.Coerce(int), vol.Range(
                    min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL
                )),
                vol.Required(
                    CONF_OFFLINE_RETRY_INTERVAL,
                    default=DEFAULT_OFFLINE_RETRY_INTERVAL,
                ): vol.All(vol.Coerce(int), vol.Range(
                    min=MIN_OFFLINE_RETRY_INTERVAL, max=MAX_OFFLINE_RETRY_INTERVAL
                )),
            }),
            description_placeholders={
                "name": self._discovered_name,
                "host": self._discovered_host,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> KefConnectorOptionsFlow:
        """Get the options flow for this handler."""
        return KefConnectorOptionsFlow(config_entry)


class KefConnectorOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for KEF Connector."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._profiles: dict = {}
        self._mac_formatted: str | None = None

    async def _async_get_coordinator(self):
        """Get the coordinator for this config entry."""
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def _async_load_profiles(self) -> dict:
        """Load saved profiles from storage."""
        coordinator = await self._async_get_coordinator()
        if not coordinator:
            return {}

        mac_address = await coordinator.speaker.mac_address
        self._mac_formatted = format_mac(mac_address).replace(":", "")

        store = Store(self.hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{self._mac_formatted}")
        data = await store.async_load()
        return data.get("profiles", {}) if data else {}

    async def _async_save_profiles(self, profiles: dict) -> None:
        """Save profiles to storage."""
        if not self._mac_formatted:
            return
        store = Store(self.hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{self._mac_formatted}")
        await store.async_save({"profiles": profiles})

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initial step - show menu of options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "volume_settings", "eq_profiles"],
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage general settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(
                    min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL
                )),
                vol.Required(
                    CONF_OFFLINE_RETRY_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_OFFLINE_RETRY_INTERVAL, DEFAULT_OFFLINE_RETRY_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(
                    min=MIN_OFFLINE_RETRY_INTERVAL, max=MAX_OFFLINE_RETRY_INTERVAL
                )),
            }),
        )

    async def async_step_volume_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Volume settings menu - choose what to configure."""
        # Get current status to show in description
        coordinator = await self._async_get_coordinator()
        current_mode = "All Sources"
        if coordinator:
            try:
                startup_enabled = await coordinator.speaker.get_startup_volume_enabled()
                if startup_enabled:
                    use_global = await coordinator.speaker.get_standby_volume_behavior()
                    current_mode = "All Sources" if use_global else "Individual Sources"
                else:
                    current_mode = "Disabled"
            except Exception:
                pass

        return self.async_show_menu(
            step_id="volume_settings",
            menu_options=[
                "volume_limits",
                "startup_volume_global",
                "startup_volume_per_input",
                "startup_volume_disable",
            ],
            description_placeholders={
                "current_mode": current_mode,
            },
        )

    async def async_step_volume_limits(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure volume limits and step size."""
        coordinator = await self._async_get_coordinator()
        if not coordinator:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            speaker = coordinator.speaker

            # Set volume limit enabled (must be set before max_volume to have effect)
            limit_enabled = user_input.get("volume_limit_enabled")
            if limit_enabled is not None:
                await speaker.set_volume_settings(limit=limit_enabled)

            # Set maximum volume
            max_vol = user_input.get("maximum_volume")
            if max_vol is not None:
                await speaker.set_volume_settings(max_volume=int(max_vol))

            # Set volume step (1-10)
            vol_step = user_input.get("volume_step")
            if vol_step is not None:
                await speaker.set_volume_settings(step=int(vol_step))

            await coordinator.async_request_refresh()
            _LOGGER.info("Updated speaker volume limits")
            return self.async_abort(reason="volume_settings_saved")

        # Get current settings from speaker
        try:
            volume_settings = await coordinator.speaker.get_volume_settings()
        except Exception:
            volume_settings = {}

        current_max = volume_settings.get("max_volume", 100)
        current_step = volume_settings.get("step", 5)
        current_limit_enabled = volume_settings.get("limit_enabled", True)

        return self.async_show_form(
            step_id="volume_limits",
            data_schema=vol.Schema({
                vol.Required(
                    "volume_limit_enabled",
                    default=current_limit_enabled,
                ): bool,
                vol.Required(
                    "maximum_volume",
                    default=current_max,
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                vol.Required(
                    "volume_step",
                    default=current_step,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
            }),
        )

    async def async_step_startup_volume_global(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set global startup volume (same volume for all inputs)."""
        coordinator = await self._async_get_coordinator()
        if not coordinator:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            # Set global mode first, then enable startup volume feature
            await coordinator.speaker.set_standby_volume_behavior(True)
            await coordinator.speaker.set_startup_volume_enabled(True)

            # Set global startup volume
            startup_vol = user_input.get("startup_volume_global")
            if startup_vol is not None:
                await coordinator.speaker.set_default_volume("global", int(startup_vol))

            await coordinator.async_request_refresh()
            _LOGGER.info("Updated speaker startup volume (global mode)")
            return self.async_abort(reason="volume_settings_saved")

        # Get current global volume
        try:
            default_volumes = await coordinator.speaker.get_all_default_volumes()
        except Exception:
            default_volumes = {}

        return self.async_show_form(
            step_id="startup_volume_global",
            data_schema=vol.Schema({
                vol.Required(
                    "startup_volume_global",
                    default=default_volumes.get("global", 30),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            }),
        )

    async def async_step_startup_volume_per_input(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set per-input startup volumes (different volume for each input)."""
        coordinator = await self._async_get_coordinator()
        if not coordinator:
            return self.async_abort(reason="cannot_connect")

        # Get speaker model to determine available inputs
        speaker_model = self.config_entry.data.get(CONF_SPEAKER_MODEL, "LSX2").upper()

        # Input sources per model (must match const.py SOURCES)
        model_inputs = {
            "LSX2": ["wifi", "bluetooth", "tv", "optical", "analog", "usb"],
            "LSX2LT": ["wifi", "bluetooth", "tv", "optical", "usb"],
            "LS50W2": ["wifi", "bluetooth", "tv", "optical", "coaxial", "analog"],
            "LS60": ["wifi", "bluetooth", "tv", "optical", "coaxial", "analog"],
            "XIO": ["wifi", "bluetooth", "tv", "optical"],
        }
        available_inputs = model_inputs.get(speaker_model, model_inputs["LSX2"])

        if user_input is not None:
            # Set per-input mode first, then enable startup volume feature
            await coordinator.speaker.set_standby_volume_behavior(False)
            await coordinator.speaker.set_startup_volume_enabled(True)

            # Set per-input startup volumes
            for input_source in available_inputs:
                key = f"startup_volume_{input_source}"
                if key in user_input:
                    await coordinator.speaker.set_default_volume(input_source, int(user_input[key]))

            await coordinator.async_request_refresh()
            _LOGGER.info("Updated speaker startup volumes (per-input mode)")
            return self.async_abort(reason="volume_settings_saved")

        # Get current per-input volumes
        try:
            default_volumes = await coordinator.speaker.get_all_default_volumes()
        except Exception:
            default_volumes = {}

        # Build schema with per-input startup volumes
        schema_dict = {}
        for input_source in available_inputs:
            schema_dict[vol.Required(
                f"startup_volume_{input_source}",
                default=default_volumes.get(input_source, 30),
            )] = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))

        return self.async_show_form(
            step_id="startup_volume_per_input",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_startup_volume_disable(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Disable startup volume (speaker resumes at last volume)."""
        coordinator = await self._async_get_coordinator()
        if not coordinator:
            return self.async_abort(reason="cannot_connect")

        # Disable startup volume feature
        await coordinator.speaker.set_startup_volume_enabled(False)
        await coordinator.async_request_refresh()
        _LOGGER.info("Disabled startup volume (speaker will resume at last volume)")
        return self.async_abort(reason="startup_volume_disabled")

    async def async_step_eq_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """EQ Profile management menu."""
        # Load profiles for display
        self._profiles = await self._async_load_profiles()

        return self.async_show_menu(
            step_id="eq_profiles",
            menu_options=["save_profile", "load_profile", "delete_profile"],
            description_placeholders={
                "profile_count": str(len(self._profiles)),
                "profile_names": ", ".join(self._profiles.keys()) if self._profiles else "None",
            },
        )

    async def async_step_save_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Save current EQ settings as a new profile."""
        errors = {}

        if user_input is not None:
            profile_name = user_input.get("profile_name", "").strip()
            description = user_input.get("description", "").strip()

            if not profile_name:
                errors["profile_name"] = "name_required"
            else:
                # Load current profiles
                self._profiles = await self._async_load_profiles()

                # Get current EQ profile from speaker
                coordinator = await self._async_get_coordinator()
                if coordinator:
                    eq_profile = await coordinator.speaker.get_eq_profile()

                    # Save with metadata
                    self._profiles[profile_name] = {
                        "eq_profile": eq_profile,
                        "description": description,
                        "created": datetime.now().isoformat(),
                        "modified": datetime.now().isoformat(),
                    }
                    await self._async_save_profiles(self._profiles)

                    # Trigger coordinator refresh so EQ profile select entity reloads
                    await coordinator.async_request_refresh()

                    _LOGGER.info("Saved EQ profile '%s'", profile_name)
                    return self.async_abort(reason="profile_saved")

        # Get current profile name from speaker for suggestion
        coordinator = await self._async_get_coordinator()
        current_name = ""
        if coordinator and coordinator.data:
            current_name = coordinator.data.get("eq_profile_name", "")

        return self.async_show_form(
            step_id="save_profile",
            data_schema=vol.Schema({
                vol.Required("profile_name", default=current_name): str,
                vol.Optional("description", default=""): str,
            }),
            errors=errors,
        )

    async def async_step_load_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Load a saved EQ profile."""
        self._profiles = await self._async_load_profiles()

        if not self._profiles:
            return self.async_abort(reason="no_profiles")

        if user_input is not None:
            profile_name = user_input.get("profile_name")
            if profile_name and profile_name in self._profiles:
                coordinator = await self._async_get_coordinator()
                if coordinator:
                    eq_profile = self._profiles[profile_name].get("eq_profile")
                    if eq_profile:
                        await coordinator.speaker.set_eq_profile(eq_profile)
                        await coordinator.async_request_refresh()
                        _LOGGER.info("Loaded EQ profile '%s'", profile_name)
                        return self.async_abort(reason="profile_loaded")

        # Build options list with descriptions
        profile_options = []
        for name, data in self._profiles.items():
            desc = data.get("description", "")
            label = f"{name} ({desc})" if desc else name
            profile_options.append(selector.SelectOptionDict(value=name, label=label))

        return self.async_show_form(
            step_id="load_profile",
            data_schema=vol.Schema({
                vol.Required("profile_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=profile_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_delete_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Delete a saved EQ profile."""
        self._profiles = await self._async_load_profiles()

        if not self._profiles:
            return self.async_abort(reason="no_profiles")

        if user_input is not None:
            profile_name = user_input.get("profile_name")
            if profile_name and profile_name in self._profiles:
                del self._profiles[profile_name]
                await self._async_save_profiles(self._profiles)

                # Trigger coordinator refresh so EQ profile select entity reloads
                coordinator = await self._async_get_coordinator()
                if coordinator:
                    await coordinator.async_request_refresh()

                _LOGGER.info("Deleted EQ profile '%s'", profile_name)
                return self.async_abort(reason="profile_deleted")

        # Build options list
        profile_options = list(self._profiles.keys())

        return self.async_show_form(
            step_id="delete_profile",
            data_schema=vol.Schema({
                vol.Required("profile_name"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=profile_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )
