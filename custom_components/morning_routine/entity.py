"""The base of every entity. The routine pushes changes, so nothing polls."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from custom_components.morning_routine import RoutineConfigEntry
from custom_components.morning_routine.const import DOMAIN


class RoutineEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: RoutineConfigEntry, key: str) -> None:
        self.routine = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.routine.add_listener(self.async_write_ha_state))
