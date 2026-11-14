"""Builds the view of one routine that the card draws."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.util import dt as dt_util

from custom_components.morning_routine.const import (
    ALLOWED_DOMAINS,
    CONF_ALARM_SENSOR,
    DEVICE_DOMAINS,
    LABEL_NAME,
    MAX_OFFSET_MINUTES,
    MIN_OFFSET_MINUTES,
)
from custom_components.morning_routine.devices import RUN_ACTIONS, describe_device, step_detail
from custom_components.morning_routine.routine import step_is_allowed
from custom_components.morning_routine.rules import RECORD_KEPT


def build_view(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    routine = entry.runtime_data
    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "is_on": routine.is_on,
        "skip_next": routine.skip_next,
        "clock": routine.clock,
        "clock_options": [{"package": package, "name": name} for package, name in routine.clock_options.items()],
        "steps": [
            {
                # What the card calls the step when it sends a change back.
                "id": step.key,
                "item": step.item,
                "name": _name(hass, step.item),
                "offset_minutes": step.offset_minutes,
                "enabled": step.enabled,
                "available": step_is_allowed(hass, step),
                "action": step.action,
                "brightness": step.brightness,
                "temperature": step.temperature,
                "heat_to": step.heat_to,
                "cool_to": step.cool_to,
                # What the step does, in words, so the card needs no device words of its own.
                "detail": step_detail(hass, step),
            }
            for step in routine.steps
        ],
        "items": sorted(
            _labeled_items(hass) + _devices(hass), key=lambda item: (item["name"].casefold(), item["item"])
        ),
        "problems": _problems(hass, entry),
        "min_offset_minutes": MIN_OFFSET_MINUTES,
        "max_offset_minutes": MAX_OFFSET_MINUTES,
    }


def _name(hass: HomeAssistant, item: str) -> str:
    state = hass.states.get(item)
    if state is not None:
        return state.name
    registry_entry = er.async_get(hass).async_get(item)
    if registry_entry is None:
        return item
    return registry_entry.name or registry_entry.original_name or item


def _labeled_items(hass: HomeAssistant) -> list[dict[str, Any]]:
    label = lr.async_get(hass).async_get_label_by_name(LABEL_NAME)
    if label is None:
        return []
    return [
        {"item": registry_entry.entity_id, "name": _name(hass, registry_entry.entity_id), "actions": RUN_ACTIONS}
        for registry_entry in er.async_entries_for_label(er.async_get(hass), label.label_id)
        if registry_entry.domain in ALLOWED_DOMAINS
    ]


def _devices(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Every light and thermostat a step can change, with what a step can do to it. These need no label."""
    registry = er.async_get(hass)
    devices = []
    for state in hass.states.async_all(DEVICE_DOMAINS):
        registry_entry = registry.async_get(state.entity_id)
        if registry_entry is not None and registry_entry.hidden_by is not None:
            continue
        actions = describe_device(hass, state.entity_id)
        if actions is not None:
            devices.append({"item": state.entity_id, "name": state.name, "actions": actions})
    return devices


def _problems(hass: HomeAssistant, entry: ConfigEntry) -> list[str]:
    problems: list[str] = []
    sensor_id = entry.data[CONF_ALARM_SENSOR]
    sensor = er.async_get(hass).async_get(sensor_id)
    if sensor is None or sensor.disabled:
        problems.append("sensor_missing")
    else:
        # A phone with no alarm set reports unavailable, which isn't a problem.
        state = hass.states.get(sensor_id)
        time = None if state is None else dt_util.parse_datetime(state.state)
        if time is not None and dt_util.as_utc(time) < dt_util.utcnow() - RECORD_KEPT:
            problems.append("sensor_stale")
    if entry.runtime_data.clock is None:
        problems.append("no_clock")
    return problems
