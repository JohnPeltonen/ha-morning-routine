"""Diagnostic sensors: the alarm being followed and the last entry that was ignored."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RoutineConfigEntry
from .entity import RoutineEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RoutineConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([CurrentAlarmSensor(entry), LastIgnoredEntrySensor(entry)])


class CurrentAlarmSensor(RoutineEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: RoutineConfigEntry) -> None:
        super().__init__(entry, "current_alarm")

    @property
    def native_value(self) -> datetime | None:
        return self.routine.current_alarm


class LastIgnoredEntrySensor(RoutineEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: RoutineConfigEntry) -> None:
        super().__init__(entry, "last_ignored_entry")

    @property
    def native_value(self) -> datetime | None:
        ignored = self.routine.last_ignored
        return None if ignored is None else ignored.time

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        ignored = self.routine.last_ignored
        if ignored is None:
            return None
        return {"package": ignored.package, "reason": ignored.reason.value}
