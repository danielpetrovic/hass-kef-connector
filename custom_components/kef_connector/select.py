"""Select platform for KEF Connector integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .const import (
    AUDIO_POLARITY_OPTIONS,
    BASS_EXTENSION_MODES,
    CABLE_MODES,
    DOMAIN,
    MASTER_CHANNELS,
    MODEL_FEATURES,
    SOUND_PROFILES,
    STANDBY_MODES,
    SUBWOOFER_PRESETS,
    WAKE_SOURCE_OPTIONS,
)
from .coordinator import KefCoordinator
from .entity import KefBaseEntity

_LOGGER = logging.getLogger(__name__)

# Storage constants (must match __init__.py)
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.profiles"


@dataclass(frozen=True, kw_only=True)
class KefSelectEntityDescription(SelectEntityDescription):
    """Describes a KEF select entity."""

    data_key: str
    set_method: str
    options_list: list[str]
    requires_feature: str | None = None


SELECT_DESCRIPTIONS: tuple[KefSelectEntityDescription, ...] = (
    KefSelectEntityDescription(
        key="bass_extension",
        translation_key="bass_extension",
        data_key="bass_extension",
        set_method="set_bass_extension",
        options_list=BASS_EXTENSION_MODES,
        icon="mdi:speaker-wireless",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSelectEntityDescription(
        key="audio_polarity",
        translation_key="audio_polarity",
        data_key="audio_polarity",
        set_method="set_audio_polarity",
        options_list=AUDIO_POLARITY_OPTIONS,
        icon="mdi:swap-horizontal",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSelectEntityDescription(
        key="subwoofer_preset",
        translation_key="subwoofer_preset",
        data_key="subwoofer_preset",
        set_method="set_subwoofer_preset",
        options_list=SUBWOOFER_PRESETS,
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSelectEntityDescription(
        key="subwoofer_polarity",
        translation_key="subwoofer_polarity",
        data_key="subwoofer_polarity",
        set_method="set_subwoofer_polarity",
        options_list=AUDIO_POLARITY_OPTIONS,
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSelectEntityDescription(
        key="standby_mode",
        translation_key="standby_mode",
        data_key="standby_mode",
        set_method="set_standby_mode",
        options_list=list(STANDBY_MODES.keys()),
        icon="mdi:power-sleep",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSelectEntityDescription(
        key="cable_mode",
        translation_key="cable_mode",
        data_key="cable_mode",
        set_method="set_cable_mode",
        options_list=CABLE_MODES,
        icon="mdi:cable-data",
        entity_category=EntityCategory.CONFIG,
        requires_feature="cable_mode",
    ),
    KefSelectEntityDescription(
        key="master_channel",
        translation_key="master_channel",
        data_key="master_channel",
        set_method="set_master_channel",
        options_list=MASTER_CHANNELS,
        icon="mdi:speaker-multiple",
        entity_category=EntityCategory.CONFIG,
        requires_feature="stereo_pair",
    ),
    KefSelectEntityDescription(
        key="sound_profile",
        translation_key="sound_profile",
        data_key="sound_profile",
        set_method="set_sound_profile",
        options_list=SOUND_PROFILES,
        icon="mdi:surround-sound",
        entity_category=None,  # Controls - frequently used during playback
        requires_feature="sound_profile",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF Connector select entities from config entry."""
    coordinator: KefCoordinator = hass.data[DOMAIN][entry.entry_id]
    speaker_model = entry.data.get("speaker_model", "LSX2").upper()
    features = MODEL_FEATURES.get(speaker_model, MODEL_FEATURES["LSX2"])

    entities: list[SelectEntity] = []

    for description in SELECT_DESCRIPTIONS:
        # Check if feature is required and available
        if description.requires_feature:
            if not features.get(description.requires_feature):
                continue

        entities.append(KefSelectEntity(coordinator, entry, description))

    # Add EQ Profile select entity (available for all speakers)
    entities.append(KefEqProfileSelectEntity(hass, coordinator, entry))

    # Add Wake Source select entity with model-specific options
    wake_source_options = WAKE_SOURCE_OPTIONS.get(speaker_model, WAKE_SOURCE_OPTIONS["LSX2"])
    wake_source_desc = KefSelectEntityDescription(
        key="wake_source",
        translation_key="wake_source",
        data_key="wake_source",
        set_method="set_wake_source",
        options_list=wake_source_options,
        icon="mdi:power",
        entity_category=EntityCategory.CONFIG,
    )
    entities.append(KefSelectEntity(coordinator, entry, wake_source_desc))

    async_add_entities(entities)


class KefSelectEntity(KefBaseEntity, SelectEntity):
    """Representation of a KEF select entity."""

    entity_description: KefSelectEntityDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        entry: ConfigEntry,
        description: KefSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        self._attr_options = description.options_list

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if not self.coordinator.last_update_success:
            return None
        value = self.coordinator.data.get(self.entity_description.data_key)
        if value is None:
            return None
        # Ensure value is in options list
        if value in self._attr_options:
            return value
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        speaker = self.coordinator.speaker
        method = getattr(speaker, self.entity_description.set_method)
        await method(option)

        # Special handling for subwoofer preset: KEF speaker changes multiple settings
        # (gain, crossover, polarity, etc.) when preset changes, so we need to refresh
        if self.entity_description.key == "subwoofer_preset":
            # Give the speaker time to apply preset changes before refreshing
            # KEF speakers need ~1 second to commit all preset adjustments
            await asyncio.sleep(1.0)
            # Force full refresh to get all updated subwoofer settings
            await self.coordinator.async_request_refresh()
        else:
            # Optimistically update the UI immediately for other selects
            self.coordinator.async_set_updated_data_optimistic(
                self.entity_description.data_key, option
            )


class KefEqProfileSelectEntity(KefBaseEntity, SelectEntity):
    """Select entity for EQ profiles.

    Shows the current active profile name from the speaker.
    When saved profiles exist in HA storage, allows switching between them.
    The current speaker profile is always shown, plus any saved profiles.
    """

    _attr_icon = "mdi:equalizer"
    _attr_translation_key = "eq_profile"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KefCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the EQ profile select entity."""
        super().__init__(coordinator, entry, "eq_profile")
        self.hass = hass
        self._store: Store | None = None
        self._saved_profiles: dict = {}

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        # Load saved profiles from storage
        await self._async_load_saved_profiles()

    async def _async_load_saved_profiles(self) -> None:
        """Load saved profiles from HA storage."""
        mac_address = await self.coordinator.speaker.mac_address
        mac_formatted = format_mac(mac_address).replace(":", "")

        self._store = Store(
            self.hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{mac_formatted}"
        )
        data = await self._store.async_load()

        if data and "profiles" in data:
            self._saved_profiles = data["profiles"]
        else:
            self._saved_profiles = {}

        self.async_write_ha_state()

    @property
    def options(self) -> list[str]:
        """Return the list of available profiles.

        Includes the current speaker profile name plus any saved profiles.
        """
        options = []

        # Add current speaker profile name
        current_name = self.coordinator.data.get("eq_profile_name") if self.coordinator.data else None
        if current_name:
            options.append(current_name)

        # Add saved profiles (excluding the current one to avoid duplicates)
        for name in self._saved_profiles.keys():
            if name not in options:
                options.append(name)

        return options

    @property
    def current_option(self) -> str | None:
        """Return the current active profile name from the speaker."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return None
        return self.coordinator.data.get("eq_profile_name")

    async def async_select_option(self, option: str) -> None:
        """Load and apply a saved EQ profile."""
        # If selecting the current profile, nothing to do
        current_name = self.coordinator.data.get("eq_profile_name") if self.coordinator.data else None
        if option == current_name:
            _LOGGER.debug("Profile '%s' is already active", option)
            return

        # Check if this is a saved profile we can load
        if option not in self._saved_profiles:
            _LOGGER.error("Profile '%s' not found in saved profiles", option)
            return

        # Get the EQ profile data
        eq_profile = self._saved_profiles[option].get("eq_profile")
        if not eq_profile:
            _LOGGER.error("Profile '%s' has no EQ data", option)
            return

        # Apply to speaker
        await self.coordinator.speaker.set_eq_profile(eq_profile)

        # Refresh coordinator to update all entities
        await self.coordinator.async_request_refresh()

        _LOGGER.info("Loaded EQ profile '%s'", option)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        Reload saved profiles in case they changed via config flow.
        """
        # Schedule async reload of profiles (can't await in sync callback)
        self.hass.async_create_task(self._async_load_saved_profiles())
        super()._handle_coordinator_update()
