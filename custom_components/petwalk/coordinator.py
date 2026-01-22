"""DataUpdateCoordinator per PetWALK."""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow
from aiohttp import ClientError, ClientResponseError
from .const import (
    CONF_INCLUDE_ALL_EVENTS,
    CONF_PORT,
    COORDINATOR_KEY_API_DATA,
    COORDINATOR_KEY_PET_STATUS,
    DEFAULT_INCLUDE_ALL_EVENTS,
    DEFAULT_PORT,
    DOMAIN,
    MANUFACTURER,
)
from .petwalk_api import PetwalkClient
_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(seconds=5)
UPDATE_INTERVAL_PET = timedelta(seconds=120)
class PetwalkCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """PetWALK coordinator."""
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.entry = entry
        self.client = PetwalkClient(
            host=entry.data[CONF_IP_ADDRESS],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        )
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_IP_ADDRESS])},
            name=entry.title,
            manufacturer=MANUFACTURER,
        )
    async def initialize(self) -> None:
        """First setup."""
        try:
            modes = await self.client.get_modes()
            states = await self.client.get_states()
            _LOGGER.debug("Initial states from API: %s", states)
        except Exception as err:
            raise ConfigEntryNotReady from err
        # Aggiorniamo subito i dati
        await self.async_config_entry_first_refresh()
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._device_info
    async def set_mode(self, key: str, value: bool) -> None:
        """Change single mode."""
        await self.client.set_modes(**{key: value})
        # Aspetta un attimo prima di aggiornare per dare tempo all'API
        await asyncio.sleep(0.5)
        await self.async_request_refresh()
    async def set_state(self, key: str, value: bool) -> None:
        """Change door/system state."""
        if key == "door":
            await self.client.set_states(door="open" if value else "closed")
            await asyncio.sleep(0.5)
            await self.async_request_refresh()
        elif key == "system":
            command = "on" if value else "off"
            _LOGGER.debug("Invio comando system: %s", command)
            
            try:
                await self.client.set_states(system=command)
                # Aspetta che il dispositivo elabori il comando
                await asyncio.sleep(1)
                # Forza un refresh immediato
                await self.async_request_refresh()
            except (ClientError, asyncio.TimeoutError) as err:
                _LOGGER.error("Errore durante il cambio stato system: %s", err)
                raise
        else:
            _LOGGER.warning("Unknown state key %s", key)
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data."""
        try:
            async with asyncio.timeout(10):
                data = self.data or {}
                
                modes = await self.client.get_modes()
                states = await self.client.get_states()
                
                # Normalizza lo stato system: converte stringhe in booleani
                if "system" in states:
                    if isinstance(states["system"], str):
                        states["system"] = states["system"].lower() in ("on", "true", "1")
                    elif isinstance(states["system"], int):
                        states["system"] = bool(states["system"])
                
                # Per door manteniamo la stringa "open"/"closed" per la cover
                # Non fare conversione a booleano
                
                _LOGGER.debug("States ricevuti dall'API: %s", states)
                
                api_data = {**modes, **states}
                data[COORDINATOR_KEY_API_DATA] = api_data
                
                # Pet status mock
                if COORDINATOR_KEY_PET_STATUS not in data:
                    data[COORDINATOR_KEY_PET_STATUS] = {}
                
                return data
                
        except Exception as err:
            _LOGGER.error("Errore comunicazione API: %s", err)
            raise UpdateFailed(f"Errore comunicazione API: {err}") from err
