"""Device tracker per PetWALK."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import COORDINATOR_KEY_PET_STATUS, DOMAIN, NAME, ZONE_HOME
from .coordinator import PetwalkCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up device tracker."""
    coordinator: PetwalkCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_pet_ids: set[str] = set()

    @callback
    def _async_add_pets() -> None:
        """Add tracker entities only for pets that are actually available."""
        new_entities: list[PetwalkDeviceTracker] = []

        for pet in coordinator.pets:
            if pet.id in known_pet_ids:
                continue

            # Do not create entities for unknown/unnamed pets.
            if pet.unknown or not pet.name:
                continue

            known_pet_ids.add(pet.id)
            new_entities.append(
                PetwalkDeviceTracker(
                    coordinator,
                    pet_id=pet.id,
                    species=pet.species,
                    entity_name=pet.name,
                )
            )

        if new_entities:
            add_entities(new_entities, True)

    # Create entities for pets already known at startup.
    _async_add_pets()

    # If pets become available later, add entities dynamically.
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_pets)
    )


class PetwalkDeviceTracker(CoordinatorEntity[PetwalkCoordinator], TrackerEntity):
    """Pet device tracker."""

    _attr_source_type = SourceType.ROUTER

    def __init__(
        self,
        coordinator: PetwalkCoordinator,
        pet_id: str,
        species: str | None,
        entity_name: str,
    ) -> None:
        """Init."""
        super().__init__(coordinator)
        self._pet_id = pet_id

        device_name = coordinator.device_info["name"]

        self._attr_name = f"{NAME} {device_name} {entity_name}"
        self._attr_unique_id = (
            f"{DOMAIN}_{slugify(device_name)}_pet_{slugify(str(pet_id))}"
        )
        self._attr_device_info = coordinator.device_info
        self._attr_icon = {
            "cat": "mdi:cat",
            "dog": "mdi:dog",
        }.get((species or "").lower(), "mdi:paw")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and any(
            pet.id == self._pet_id for pet in self.coordinator.pets
        )

    def _event_value(self, key: str) -> Any:
        """Read a value from the current pet status event."""
        data = self.coordinator.data or {}
        pet_status = data.get(COORDINATOR_KEY_PET_STATUS, {})
        event = pet_status.get(self._pet_id)

        if not event:
            return None

        if isinstance(event, dict):
            return event.get(key)

        return getattr(event, key, None)

    @property
    def in_zones(self) -> list[str] | None:
        """Return zones where the pet is currently located.

        This replaces the deprecated location_name property.
        Home Assistant derives home/not_home from this list.
        """
        # If a specific zone entity_id is provided, use it.
        zone = self._event_value("zone_entity_id") or self._event_value("zone")
        if zone:
            return [str(zone)]

        # Explicit home boolean.
        home = self._event_value("home")
        if home is True:
            return [ZONE_HOME]
        if home is False:
            return []

        # PetWALK direction mock/future support:
        # - "in"  -> pet entered home
        # - "out" -> pet left home
        direction = self._event_value("direction")
        if direction == "in":
            return [ZONE_HOME]
        if direction == "out":
            return []

        # No explicit zone information: let Home Assistant fall back to
        # coordinates if they are provided.
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude if available."""
        for key in ("latitude", "lat"):
            value = self._event_value(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude if available."""
        for key in ("longitude", "lon", "lng"):
            value = self._event_value(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    @property
    def location_accuracy(self) -> float:
        """Return location accuracy if available."""
        value = self._event_value("accuracy") or self._event_value("location_accuracy")
        if value is None:
            return 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0
