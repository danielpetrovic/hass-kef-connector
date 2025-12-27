"""Switch platform for KEF Connector integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODEL_FEATURES
from .coordinator import KefCoordinator
from .entity import KefBaseEntity


@dataclass(frozen=True, kw_only=True)
class KefSwitchEntityDescription(SwitchEntityDescription):
    """Describes a KEF switch entity."""

    data_key: str
    set_on_method: str
    set_off_method: str | None = None
    requires_feature: str | None = None
    enabled_default: bool = True
    inverted: bool = False  # If True, switch ON means API value is False


SWITCH_DESCRIPTIONS: tuple[KefSwitchEntityDescription, ...] = (
    # DSP switches (bookshelf speakers only - not LS60/XIO)
    KefSwitchEntityDescription(
        key="desk_mode",
        translation_key="desk_mode",
        data_key="desk_mode_enabled",
        set_on_method="set_desk_mode",
        icon="mdi:desk",
        entity_category=EntityCategory.CONFIG,
        requires_feature="desk_mode",
    ),
    KefSwitchEntityDescription(
        key="wall_mode",
        translation_key="wall_mode",
        data_key="wall_mode_enabled",
        set_on_method="set_wall_mode",
        icon="mdi:wall",
        entity_category=EntityCategory.CONFIG,
        requires_feature="wall_mode",
    ),
    KefSwitchEntityDescription(
        key="phase_correction",
        translation_key="phase_correction",
        data_key="phase_correction",
        set_on_method="set_phase_correction",
        icon="mdi:sine-wave",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSwitchEntityDescription(
        key="high_pass_mode",
        translation_key="high_pass_mode",
        data_key="high_pass_enabled",
        set_on_method="set_high_pass_filter",
        icon="mdi:filter-variant",
        entity_category=EntityCategory.CONFIG,
    ),
    # Subwoofer switches
    KefSwitchEntityDescription(
        key="subwoofer",
        translation_key="subwoofer",
        data_key="subwoofer_enabled",
        set_on_method="set_subwoofer_enabled",
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
    ),
    # Note: subwoofer_stereo removed - API field exists but has no effect
    # Wireless subwoofer adapter (KW1)
    KefSwitchEntityDescription(
        key="kw1_adapter",
        translation_key="kw1_adapter",
        data_key="kw1_enabled",
        set_on_method="set_kw1_enabled",
        icon="mdi:wifi",
        entity_category=EntityCategory.CONFIG,
    ),
    # Subwoofer wake on startup (wired subwoofers)
    KefSwitchEntityDescription(
        key="subwoofer_wake_on_startup",
        translation_key="subwoofer_wake_on_startup",
        data_key="subwoofer_wake_on_startup",
        set_on_method="set_subwoofer_wake_on_startup",
        icon="mdi:power",
        entity_category=EntityCategory.CONFIG,
    ),
    # KW1 wake on startup (KC62/KF92 wireless subwoofers)
    KefSwitchEntityDescription(
        key="kw1_wake_on_startup",
        translation_key="kw1_wake_on_startup",
        data_key="kw1_wake_on_startup",
        set_on_method="set_kw1_wake_on_startup",
        icon="mdi:power",
        entity_category=EntityCategory.CONFIG,
    ),
    # XIO-specific switches
    KefSwitchEntityDescription(
        key="wall_mounted",
        translation_key="wall_mounted",
        data_key="wall_mounted",
        set_on_method="set_wall_mounted",
        icon="mdi:wall",
        entity_category=EntityCategory.CONFIG,
        requires_feature="sound_profile",  # XIO feature
    ),
    # LED switches
    KefSwitchEntityDescription(
        key="front_led",
        translation_key="front_led",
        data_key="front_led",
        set_on_method="set_front_led",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        requires_feature="front_led",  # LSX II LT has no illuminated logo
    ),
    KefSwitchEntityDescription(
        key="standby_led",
        translation_key="standby_led",
        data_key="standby_led",
        set_on_method="set_standby_led",
        icon="mdi:led-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSwitchEntityDescription(
        key="control_panel_lock",
        translation_key="control_panel_lock",
        data_key="top_panel_enabled",
        set_on_method="set_top_panel_enabled",
        icon="mdi:lock",
        entity_category=EntityCategory.CONFIG,
        inverted=True,  # Lock ON = top_panel_enabled False
        requires_feature="top_panel_led",  # XIO only - has physical control panel
    ),
    KefSwitchEntityDescription(
        key="control_panel_led",
        translation_key="control_panel_led",
        data_key="top_panel_led",
        set_on_method="set_top_panel_led",
        icon="mdi:led-on",
        entity_category=EntityCategory.CONFIG,
        requires_feature="top_panel_led",
    ),
    # System switches
    KefSwitchEntityDescription(
        key="hdmi_auto_switch",
        translation_key="hdmi_auto_switch",
        data_key="auto_switch_hdmi",
        set_on_method="set_auto_switch_hdmi",
        icon="mdi:hdmi-port",
        entity_category=EntityCategory.CONFIG,
    ),
    KefSwitchEntityDescription(
        key="startup_tone",
        translation_key="startup_tone",
        data_key="startup_tone",
        set_on_method="set_startup_tone",
        icon="mdi:bell-ring",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF Connector switch entities from config entry."""
    coordinator: KefCoordinator = hass.data[DOMAIN][entry.entry_id]
    speaker_model = entry.data.get("speaker_model", "LSX2").upper()
    features = MODEL_FEATURES.get(speaker_model, MODEL_FEATURES["LSX2"])

    entities: list[KefSwitchEntity] = []

    for description in SWITCH_DESCRIPTIONS:
        # Check if feature is required and available
        if description.requires_feature:
            if not features.get(description.requires_feature):
                continue

        entities.append(KefSwitchEntity(coordinator, entry, description))

    async_add_entities(entities)


class KefSwitchEntity(KefBaseEntity, SwitchEntity):
    """Representation of a KEF switch entity."""

    entity_description: KefSwitchEntityDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        entry: ConfigEntry,
        description: KefSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        if not description.enabled_default:
            self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if not self.coordinator.last_update_success:
            return None
        value = self.coordinator.data.get(self.entity_description.data_key)
        if value is None:
            return None
        # Handle inverted switches (e.g., control panel lock: ON = disabled)
        if self.entity_description.inverted:
            return not value
        return value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        speaker = self.coordinator.speaker
        method_name = self.entity_description.set_on_method
        method = getattr(speaker, method_name)

        # Determine the actual API value (inverted switches send False when turned ON)
        api_value = not self.entity_description.inverted

        # Special handling for methods that need additional parameters
        if method_name == "set_desk_mode":
            # Preserve current dB value when turning on, default to -3dB if None
            current_db = self.coordinator.data.get("desk_mode_db")
            if current_db is None:
                current_db = -3.0
            await method(api_value, current_db)
        elif method_name == "set_wall_mode":
            # Preserve current dB value when turning on, default to -3dB if None
            current_db = self.coordinator.data.get("wall_mode_db")
            if current_db is None:
                current_db = -3.0
            await method(api_value, current_db)
        elif method_name == "set_high_pass_filter":
            # Preserve current frequency when turning on, default to 80Hz if None
            current_freq = self.coordinator.data.get("high_pass_freq")
            if current_freq is None:
                current_freq = 80.0
            await method(api_value, current_freq)
        else:
            await method(api_value)

        # Optimistically update the UI immediately
        # For inverted switches, UI "on" = data value False
        self.coordinator.async_set_updated_data_optimistic(
            self.entity_description.data_key,
            not self.entity_description.inverted
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        speaker = self.coordinator.speaker
        method_name = self.entity_description.set_on_method

        # Determine the actual API value (inverted switches send True when turned OFF)
        api_value = self.entity_description.inverted

        if self.entity_description.set_off_method:
            method = getattr(speaker, self.entity_description.set_off_method)
            await method()
        else:
            method = getattr(speaker, method_name)

            # Special handling for methods that need additional parameters
            if method_name == "set_desk_mode":
                await method(api_value, 0.0)
            elif method_name == "set_wall_mode":
                await method(api_value, 0.0)
            elif method_name == "set_high_pass_filter":
                await method(api_value, 80.0)
            else:
                await method(api_value)

        # Optimistically update the UI immediately
        # For inverted switches, UI "off" = data value True
        self.coordinator.async_set_updated_data_optimistic(
            self.entity_description.data_key,
            self.entity_description.inverted
        )
