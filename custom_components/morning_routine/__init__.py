"""Morning routines that run around a phone's alarm."""

from typing import Any

import probatio
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from custom_components.morning_routine.const import ATTR_CONFIG_ENTRY_ID, ATTR_STEPS, DOMAIN, MAX_OFFSET_MINUTES, SERVICE_SET_STEPS
from custom_components.morning_routine.routine import Routine, item_is_allowed, routine_store
from custom_components.morning_routine.rules import Step

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SET_STEPS_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string, probatio.Required(ATTR_STEPS): cv.match_all}
)
STEP_KEYS = {"item", "offset_minutes", "enabled"}

type RoutineConfigEntry = ConfigEntry[Routine]


def _refuse(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders)


def parse_steps(hass: HomeAssistant, raw: Any) -> list[Step]:
    """Check the whole list, so a refused call changes nothing."""
    if not isinstance(raw, list):
        raise _refuse("steps_not_a_list")
    steps: list[Step] = []
    seen: set[str] = set()
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict) or not {"item", "offset_minutes"} <= item.keys() <= STEP_KEYS:
            raise _refuse("invalid_step", number=str(index))
        name, offset, enabled = item["item"], item["offset_minutes"], item.get("enabled", True)
        if not isinstance(name, str) or not isinstance(enabled, bool):
            raise _refuse("invalid_step", number=str(index))
        if not item_is_allowed(hass, name):
            raise _refuse("item_not_allowed", item=name)
        if name in seen:
            raise _refuse("duplicate_item", item=name)
        if type(offset) is not int or abs(offset) > MAX_OFFSET_MINUTES:
            raise _refuse("offset_out_of_range", item=name, limit=str(MAX_OFFSET_MINUTES))
        seen.add(name)
        steps.append(Step(name, offset, enabled))
    return steps


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def set_steps(call: ServiceCall) -> None:
        entry = hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])
        if entry is None or entry.domain != DOMAIN:
            raise _refuse("entry_not_found")
        if entry.state is not ConfigEntryState.LOADED:
            raise _refuse("entry_not_loaded")
        await entry.runtime_data.async_set_steps(parse_steps(hass, call.data[ATTR_STEPS]))

    # Temporary: steps are set from Developer tools until the card exists.
    async_register_admin_service(hass, DOMAIN, SERVICE_SET_STEPS, set_steps, SET_STEPS_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RoutineConfigEntry) -> bool:
    routine = Routine(hass, entry)
    entry.runtime_data = routine
    # Loaded before any entity can change anything, so a setter can't save defaults over the file.
    await routine.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RoutineConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # A step already started finishes on its own.
        entry.runtime_data.async_stop()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: RoutineConfigEntry) -> None:
    await routine_store(hass, entry).async_remove()


async def _async_options_updated(hass: HomeAssistant, entry: RoutineConfigEntry) -> None:
    await entry.runtime_data.async_reread_sensor()
