"""The routine switch and the skip switch."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RoutineConfigEntry
from .entity import RoutineEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RoutineConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([RoutineSwitch(entry), SkipNextAlarmSwitch(entry)])


class RoutineSwitch(RoutineEntity, SwitchEntity):
    def __init__(self, entry: RoutineConfigEntry) -> None:
        super().__init__(entry, "routine")

    @property
    def is_on(self) -> bool:
        return self.routine.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.routine.async_set_on(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.routine.async_set_on(False)


class SkipNextAlarmSwitch(RoutineEntity, SwitchEntity):
    def __init__(self, entry: RoutineConfigEntry) -> None:
        super().__init__(entry, "skip_next_alarm")

    @property
    def is_on(self) -> bool:
        return self.routine.skip_next

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.routine.async_set_skip(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.routine.async_set_skip(False)
