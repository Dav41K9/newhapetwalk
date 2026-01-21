"""Switch platform per PetWALK."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR_KEY_API_DATA, DOMAIN, NAME
from .coordinator import PetwalkCoordinator

_LOGGER = logging.getLogger(__name__)

# (Friendly name, entity_id_suffix, api_key, icon)
SWITCHES = [
    ("Brightness Sensor", "brightness_sensor", "brightnessSensor", "mdi:brightness-6"),
    ("Motion IN", "motion_in", "motion_in", "mdi:account-arrow-left"),
    ("Motion OUT", "motion_out", "motion_out", "mdi:account-arrow-right"),
    ("RFID", "rfid", "rfid", "mdi:nfc-variant"),
    ("Time", "time", "time", "mdi:clock-time-eight"),
    ("System", "system", "system", "mdi:power"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up PetWALK switches."""
    coordinator: PetwalkCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    add_entities(
        PetwalkSwitch(coordinator, name, eid, key, icon)
        for name, eid, key, icon in SWITCHES
    )


class PetwalkSwitch(CoordinatorEntity[PetwalkCoordinator], SwitchEntity):
    """PetWALK switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: PetwalkCoordinator,
        entity_name: str,
        entity_id: str,
        api_key: str,
        icon: str | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._api_key = api_key
        self._attr_name = f"{NAME} {coordinator.device_info['name']} {entity_name}"
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device_info['name']}_{entity_id}"
        self._attr_device_info = coordinator.device_info
        if icon:
            self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        """Return switch state."""
        value = self.coordinator.data.get(COORDINATOR_KEY_API_DATA, {}).get(self._api_key, False)
        
        # Log per debug dello stato system
        if self._api_key == "system":
            _LOGGER.debug("Switch system is_on: valore API=%s, tipo=%s", value, type(value))
        
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        if self._api_key == "system":
            await self.coordinator.set_state("system", True)
        else:
            await self.coordinator.set_mode(self._api_key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        if self._api_key == "system":
            await self.coordinator.set_state("system", False)
        else:
            await self.coordinator.set_mode(self._api_key, False)
