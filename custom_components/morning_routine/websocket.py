"""The commands the card uses. Anyone logged in may use them."""

from typing import Any

import probatio
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, label_registry as lr

from custom_components.morning_routine.const import DOMAIN
from custom_components.morning_routine.step_input import parse_steps, refuse
from custom_components.morning_routine.view import build_view


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_set_steps)
    websocket_api.async_register_command(hass, ws_update)


def _loaded_entry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> ConfigEntry | None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "This routine isn't available.")
        return None
    return entry


@websocket_api.websocket_command(
    {probatio.Required("type"): "morning_routine/subscribe", probatio.Required("entry_id"): str}
)
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _loaded_entry(hass, connection, msg)
    if entry is None:
        return

    @callback
    def send_view(*_: Any) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], {"view": build_view(hass, entry)}))

    unsubs = [
        entry.runtime_data.add_listener(send_view),
        # Names, labels and deleted items all change what the card shows.
        hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, send_view),
        hass.bus.async_listen(lr.EVENT_LABEL_REGISTRY_UPDATED, send_view),
    ]

    @callback
    def unsubscribe() -> None:
        for unsub in unsubs:
            unsub()
        unsubs.clear()

    @callback
    def routine_unloaded() -> None:
        if not unsubs:
            return
        unsubscribe()
        connection.subscriptions.pop(msg["id"], None)
        connection.send_message(websocket_api.event_message(msg["id"], {"unavailable": True}))

    entry.async_on_unload(routine_unloaded)
    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send_view()


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "morning_routine/set_steps",
        probatio.Required("entry_id"): str,
        probatio.Required("steps"): list,
    }
)
@websocket_api.async_response
async def ws_set_steps(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _loaded_entry(hass, connection, msg)
    if entry is None:
        return
    routine = entry.runtime_data
    keep = frozenset(step.item for step in routine.steps)
    await routine.async_set_steps(parse_steps(hass, msg["steps"], keep))
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "morning_routine/update",
        probatio.Required("entry_id"): str,
        probatio.Optional("is_on"): bool,
        probatio.Optional("skip_next"): bool,
        probatio.Optional("clock"): str,
    }
)
@websocket_api.async_response
async def ws_update(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    entry = _loaded_entry(hass, connection, msg)
    if entry is None:
        return
    routine = entry.runtime_data
    # Checked before anything changes, so a refused command changes nothing.
    if "clock" in msg and msg["clock"] not in routine.clock_options:
        raise refuse("clock_not_offered")
    if "clock" in msg:
        await routine.async_set_clock(msg["clock"])
    if "skip_next" in msg:
        await routine.async_set_skip(msg["skip_next"])
    if "is_on" in msg:
        await routine.async_set_on(msg["is_on"])
    connection.send_result(msg["id"])
