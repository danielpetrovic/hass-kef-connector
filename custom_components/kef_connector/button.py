"""Button platform for KEF Connector integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KefCoordinator
from .entity import KefBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF Connector button entities from config entry."""
    coordinator: KefCoordinator = hass.data[DOMAIN][entry.entry_id]
    speaker_model = entry.data.get("speaker_model", "LSX2").upper()

    entities = []

    # XIO-only buttons
    if speaker_model == "XIO":
        entities.append(KefCalibrationButton(coordinator, entry))

    if entities:
        async_add_entities(entities)


class KefCalibrationButton(KefBaseEntity, ButtonEntity):
    """Button to start room calibration (XIO soundbar only)."""

    _attr_icon = "mdi:tune"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "start_calibration"

    def __init__(
        self,
        coordinator: KefCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calibration button."""
        super().__init__(coordinator, entry, "start_calibration")

    async def async_press(self) -> None:
        """Start room calibration."""
        await self.coordinator.speaker.start_calibration()
        # Request refresh to update calibration_step sensor
        await self.coordinator.async_request_refresh()
