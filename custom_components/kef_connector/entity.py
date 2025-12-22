"""Base entity for KEF Connector integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SPEAKER_MODEL,
    DOMAIN,
    MANUFACTURER,
    MODEL_FEATURES,
    MODEL_NAMES,
    UNIQUE_ID_PREFIX,
)
from .coordinator import KefCoordinator


class KefBaseEntity(CoordinatorEntity[KefCoordinator]):
    """Base class for KEF entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KefCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: The data update coordinator.
            entry: The config entry.
            key: Unique key for this entity (e.g., "treble", "desk_mode").
        """
        super().__init__(coordinator)
        self._entry = entry
        self._key = key

        # Build unique ID
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to link entity to device."""
        name = self._entry.data[CONF_NAME]
        host = self._entry.data[CONF_HOST]
        speaker_model = self._entry.data.get(CONF_SPEAKER_MODEL, "LSX2").upper()

        # Get MAC from coordinator data if available
        mac_address = self.coordinator.data.get("mac_address", "")
        if mac_address:
            mac_address = format_mac(mac_address)
        device_unique_id = f"{UNIQUE_ID_PREFIX}_{mac_address}"

        return DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            name=name,
            manufacturer=MANUFACTURER,
            model=MODEL_NAMES.get(speaker_model, f"KEF {speaker_model}"),
            connections={("ip", host)},
        )

    @property
    def speaker_model(self) -> str:
        """Return the speaker model."""
        return self._entry.data.get(CONF_SPEAKER_MODEL, "LSX2").upper()

    @property
    def model_features(self) -> dict:
        """Return the feature flags for this speaker model."""
        return MODEL_FEATURES.get(self.speaker_model, MODEL_FEATURES["LSX2"])

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
