"""DataUpdateCoordinator per PetWALK."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from aiohttp import ClientError

from .const import (
    CONF_INCLUDE_ALL_EVENTS,
    CONF_PORT,
    COORDINATOR_KEY_API_DATA,
    COORDINATOR_KEY_PETS,
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


@dataclass
class PetwalkPet:
    """Minimal pet representation."""

    id: str
    name: str | None = None
    species: str | None = None
    unknown: bool = False


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
        self._pets: list[PetwalkPet] = []

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

    @property
    def pets(self) -> list[PetwalkPet]:
        """Return configured/known pets.

        If the PetWALK API does not expose pets, or the feature is not used,
        this returns an empty list and no device_tracker entities are created.
        """
        return self._pets

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

    def _parse_pets(self, api_data: dict[str, Any]) -> list[PetwalkPet]:
        """Parse pets from API data.

        Current PetWALK local API does not expose a dedicated pets endpoint,
        so this is intentionally defensive and future-proof.

        Supported examples:
        - api_data["pets"] = [{"id": "...", "name": "...", "species": "cat"}]
        - api_data["pets"] = ["Milo", "Luna"]
        """
        raw_pets: Any = api_data.get("pets")

        if isinstance(raw_pets, dict):
            raw_pets = raw_pets.get("pets")

        if not isinstance(raw_pets, list):
            return []

        pets: list[PetwalkPet] = []

        for index, raw in enumerate(raw_pets):
            if isinstance(raw, str):
                name = raw.strip()
                if not name:
                    continue

                pet_id = f"pet_{index}_{name.lower().replace(' ', '_')}"
                pets.append(
                    PetwalkPet(
                        id=pet_id,
                        name=name,
                        species=None,
                        unknown=False,
                    )
                )
                continue

            if not isinstance(raw, dict):
                continue

            pet_id = (
                raw.get("id")
                or raw.get("uuid")
                or raw.get("name")
                or f"pet_{index}"
            )
            name = raw.get("name")
            species = raw.get("species") or raw.get("type") or raw.get("animal")
            unknown = bool(raw.get("unknown", not bool(name)))

            pets.append(
                PetwalkPet(
                    id=str(pet_id),
                    name=str(name) if name is not None else None,
                    species=str(species) if species is not None else None,
                    unknown=unknown,
                )
            )

        return pets

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data."""
        try:
            async with asyncio.timeout(10):
                data = dict(self.data or {})

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

                # Pets: se non disponibili/restano non configurati, lista vuota.
                self._pets = self._parse_pets(api_data)
                data[COORDINATOR_KEY_PETS] = [asdict(pet) for pet in self._pets]

                # Pet status mock
                if COORDINATOR_KEY_PET_STATUS not in data:
                    data[COORDINATOR_KEY_PET_STATUS] = {}

                return data

        except (ClientError, TimeoutError) as err:
            _LOGGER.debug("Errore comunicazione API: %s", err)
            raise UpdateFailed(f"Errore comunicazione API: {err}") from err
        except Exception as err:
            _LOGGER.error("Errore inatteso API: %s", err)
            raise UpdateFailed(f"Errore inatteso API: {err}") from err
