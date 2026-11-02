"""The picker for which clock app's alarms the routine follows."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RoutineConfigEntry
from .const import DOMAIN
from .entity import RoutineEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: RoutineConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([ClockSelect(entry)])


class ClockSelect(RoutineEntity, SelectEntity):
    def __init__(self, entry: RoutineConfigEntry) -> None:
        super().__init__(entry, "clock")

    @property
    def options(self) -> list[str]:
        return list(self.routine.clock_options.values())

    @property
    def current_option(self) -> str | None:
        clock = self.routine.clock
        return None if clock is None else self.routine.clock_options.get(clock)

    async def async_select_option(self, option: str) -> None:
        package = next((package for package, name in self.routine.clock_options.items() if name == option), None)
        if package is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="clock_not_found", translation_placeholders={"clock": option}
            )
        await self.routine.async_set_clock(package)
