"""Platform for PetWALK cover."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR_KEY_API_DATA, DOMAIN, NAME
from .coordinator import PetwalkCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover platform."""
    coordinator: PetwalkCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    add_entities(
        [
            PetwalkDoor(
                coordinator,
                entity_name="Door",
                entity_id="door",
                api_key="door",
                icon="mdi:door",
            )
        ]
    )


class PetwalkDoor(CoordinatorEntity[PetwalkCoordinator], CoverEntity):
    """PetWALK Door."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        coordinator: PetwalkCoordinator,
        entity_name: str,
        entity_id: str,
        api_key: str,
        icon: str | None = None,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self._api_key = api_key
        self._attr_name = f"{NAME} {coordinator.device_info['name']} {entity_name}"
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_info['name']}_{entity_id}"
        self._attr_device_info = coordinator.device_info
        if icon:
            self._attr_icon = icon

    @property
    def is_closed(self) -> bool:
        """Return True if door is closed."""
        value = self.coordinator.data.get(COORDINATOR_KEY_API_DATA, {}).get(self._api_key)
        
        # L'API restituisce "open" o "closed" come stringhe
        # Normalizza eventuali variazioni
        if isinstance(value, str):
            value_lower = value.lower()
            is_closed = value_lower == "closed"
        else:
            # Fallback: se non è una stringa, considera False come aperto
            is_closed = bool(value) if value is not None else False
        
        _LOGGER.debug("Door is_closed: valore API='%s', tipo=%s, risultato=%s", 
                     value, type(value), is_closed)
        
        return is_closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open door."""
        _LOGGER.debug("Comando apertura porta")
        await self.coordinator.set_state("door", True)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close door."""
        _LOGGER.debug("Comando chiusura porta")
        await self.coordinator.set_state("door", False)
