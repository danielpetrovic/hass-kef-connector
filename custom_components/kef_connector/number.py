"""Number platform for KEF Connector integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KefCoordinator
from .entity import KefBaseEntity


@dataclass(frozen=True, kw_only=True)
class KefNumberEntityDescription(NumberEntityDescription):
    """Describes a KEF number entity."""

    data_key: str
    set_method: str
    native_min_value: float
    native_max_value: float
    native_step: float
    requires_feature: str | None = None


NUMBER_DESCRIPTIONS: tuple[KefNumberEntityDescription, ...] = (
    KefNumberEntityDescription(
        key="treble",
        translation_key="treble",
        data_key="treble",
        set_method="set_treble_amount",
        native_min_value=-3.0,
        native_max_value=3.0,
        native_step=0.25,
        native_unit_of_measurement="dB",
        icon="mdi:music-clef-treble",
        entity_category=EntityCategory.CONFIG,
    ),
    KefNumberEntityDescription(
        key="balance",
        translation_key="balance",
        data_key="balance",
        set_method="set_balance",
        native_min_value=-30,
        native_max_value=30,
        native_step=1,
        icon="mdi:tune-vertical",
        entity_category=EntityCategory.CONFIG,
    ),
    KefNumberEntityDescription(
        key="desk_mode_db",
        translation_key="desk_mode_db",
        data_key="desk_mode_db",
        set_method="set_desk_mode",
        native_min_value=-10.0,
        native_max_value=0.0,
        native_step=0.5,
        native_unit_of_measurement="dB",
        icon="mdi:desk",
        entity_category=EntityCategory.CONFIG,
        requires_feature="desk_mode",
    ),
    KefNumberEntityDescription(
        key="wall_mode_db",
        translation_key="wall_mode_db",
        data_key="wall_mode_db",
        set_method="set_wall_mode",
        native_min_value=-10.0,
        native_max_value=0.0,
        native_step=0.5,
        native_unit_of_measurement="dB",
        icon="mdi:wall",
        entity_category=EntityCategory.CONFIG,
        requires_feature="wall_mode",
    ),
    KefNumberEntityDescription(
        key="high_pass_freq",
        translation_key="high_pass_freq",
        data_key="high_pass_freq",
        set_method="set_high_pass_filter",
        native_min_value=50.0,
        native_max_value=120.0,
        native_step=5.0,
        native_unit_of_measurement="Hz",
        icon="mdi:sine-wave",
        entity_category=EntityCategory.CONFIG,
    ),
    KefNumberEntityDescription(
        key="subwoofer_gain",
        translation_key="subwoofer_gain",
        data_key="subwoofer_gain",
        set_method="set_subwoofer_gain",
        native_min_value=-10.0,
        native_max_value=10.0,
        native_step=1.0,
        native_unit_of_measurement="dB",
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
    ),
    KefNumberEntityDescription(
        key="subwoofer_crossover",
        translation_key="subwoofer_crossover",
        data_key="subwoofer_lowpass",
        set_method="set_subwoofer_lowpass",
        native_min_value=40.0,
        native_max_value=250.0,
        native_step=5.0,
        native_unit_of_measurement="Hz",
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
    ),
    # Note: subwoofer_count removed - KW2 appears to use BLE pairing, not HTTP API
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF Connector number entities from config entry."""
    coordinator: KefCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[KefNumberEntity] = []

    for description in NUMBER_DESCRIPTIONS:
        # Check if feature is required and available
        if description.requires_feature:
            speaker_model = entry.data.get("speaker_model", "LSX2").upper()
            from .const import MODEL_FEATURES
            features = MODEL_FEATURES.get(speaker_model, MODEL_FEATURES["LSX2"])
            if not features.get(description.requires_feature):
                continue

        entities.append(KefNumberEntity(coordinator, entry, description))

    async_add_entities(entities)


class KefNumberEntity(KefBaseEntity, NumberEntity):
    """Representation of a KEF number entity."""

    entity_description: KefNumberEntityDescription
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: KefCoordinator,
        entry: ConfigEntry,
        description: KefNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.coordinator.last_update_success:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        speaker = self.coordinator.speaker
        method_name = self.entity_description.set_method
        method = getattr(speaker, method_name)

        # Special handling for methods that need additional parameters
        if method_name == "set_desk_mode":
            # set_desk_mode needs enabled state and dB value
            await method(True, value)
        elif method_name == "set_wall_mode":
            # set_wall_mode needs enabled state and dB value
            await method(True, value)
        elif method_name == "set_high_pass_filter":
            # set_high_pass_filter needs enabled state and frequency
            await method(True, value)
        else:
            await method(value)

        # Subwoofer settings: When manually changing gain or crossover,
        # KEF speaker changes preset to "custom", so we need to refresh
        if self.entity_description.key in ("subwoofer_gain", "subwoofer_crossover"):
            # Force full refresh to get updated preset and other related values
            await self.coordinator.async_request_refresh()
        else:
            # Optimistically update the UI immediately for other numbers
            self.coordinator.async_set_updated_data_optimistic(
                self.entity_description.data_key, value
            )
