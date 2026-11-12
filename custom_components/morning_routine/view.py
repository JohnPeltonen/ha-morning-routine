"""Builds the view of one routine that the card draws."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, label_registry as lr
from homeassistant.util import dt as dt_util

from custom_components.morning_routine.const import (
    ALLOWED_DOMAINS,
    CONF_ALARM_SENSOR,
    LABEL_NAME,
    MAX_OFFSET_MINUTES,
    MIN_OFFSET_MINUTES,
)
from custom_components.morning_routine.routine import item_is_allowed
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
                "item": step.item,
                "name": _name(hass, step.item),
                "offset_minutes": step.offset_minutes,
                "enabled": step.enabled,
                "available": item_is_allowed(hass, step.item),
            }
            for step in routine.steps
        ],
        "items": _labeled_items(hass),
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


def _labeled_items(hass: HomeAssistant) -> list[dict[str, str]]:
    label = lr.async_get(hass).async_get_label_by_name(LABEL_NAME)
    if label is None:
        return []
    items = [
        {"item": registry_entry.entity_id, "name": _name(hass, registry_entry.entity_id)}
        for registry_entry in er.async_entries_for_label(er.async_get(hass), label.label_id)
        if registry_entry.domain in ALLOWED_DOMAINS
    ]
    return sorted(items, key=lambda item: (item["name"].casefold(), item["item"]))


def _problems(hass: HomeAssistant, entry: ConfigEntry) -> list[str]:
    problems: list[str] = []
    if lr.async_get(hass).async_get_label_by_name(LABEL_NAME) is None:
        problems.append("no_label")
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
