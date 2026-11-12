"""Morning routines that run around a phone's alarm."""

import probatio
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from custom_components.morning_routine import websocket
from custom_components.morning_routine.card import async_register_card
from custom_components.morning_routine.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_STEPS,
    DOMAIN,
    SERVICE_SET_STEPS,
)
from custom_components.morning_routine.routine import Routine, routine_store
from custom_components.morning_routine.step_input import parse_steps, refuse

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SET_STEPS_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string, probatio.Required(ATTR_STEPS): cv.match_all}
)
type RoutineConfigEntry = ConfigEntry[Routine]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def set_steps(call: ServiceCall) -> None:
        entry = hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])
        if entry is None or entry.domain != DOMAIN:
            raise refuse("entry_not_found")
        if entry.state is not ConfigEntryState.LOADED:
            raise refuse("entry_not_loaded")
        routine = entry.runtime_data
        await routine.async_set_steps(parse_steps(hass, call.data[ATTR_STEPS], routine.steps))

    websocket.async_register(hass)
    await async_register_card(hass)
    # For admins and scripts. The card uses the WebSocket commands.
    async_register_admin_service(hass, DOMAIN, SERVICE_SET_STEPS, set_steps, SET_STEPS_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RoutineConfigEntry) -> bool:
    routine = Routine(hass, entry)
    entry.runtime_data = routine
    # Loaded before any entity can change anything, so a setter can't save defaults over the file.
    await routine.async_start()
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        # Without its entities there is no switch to turn the routine off, so it must not keep running.
        routine.async_stop()
        raise
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
