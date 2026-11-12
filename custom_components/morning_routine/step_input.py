"""Checks a list of steps that came from a person."""

import math
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.morning_routine.const import (
    ALLOWED_DOMAINS,
    DEVICE_DOMAINS,
    DOMAIN,
    MAX_OFFSET_MINUTES,
    MIN_OFFSET_MINUTES,
)
from custom_components.morning_routine.devices import device_info
from custom_components.morning_routine.routine import item_is_allowed
from custom_components.morning_routine.rules import STEP_SETTINGS, Step

STEP_KEYS = {"item", "offset_minutes", "enabled", "id", "action", *STEP_SETTINGS}
MAX_ID_LENGTH = 64


def refuse(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders)


def parse_steps(hass: HomeAssistant, raw: Any, existing: Sequence[Step] = ()) -> list[Step]:
    """Check the whole list, so a refused call changes nothing.

    `existing` is the routine's steps now. A step that is unchanged from one of them is kept
    even if its script lost the label or its device is gone, so the other steps can still be changed.
    """
    if not isinstance(raw, list):
        raise refuse("steps_not_a_list")
    old_items = {step.item for step in existing}
    # Ids the list names itself. An id given out for a step that has none must not be one of these.
    claimed = {
        entry["id"] for entry in raw if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    steps: list[Step] = []
    seen: set[str] = set()
    keys: set[str] = set()
    for index, entry in enumerate(raw, start=1):
        number = str(index)
        if not isinstance(entry, dict) or not {"item", "offset_minutes"} <= entry.keys() <= STEP_KEYS:
            raise refuse("invalid_step", number=number)
        name, offset, enabled = entry["item"], entry["offset_minutes"], entry.get("enabled", True)
        if not isinstance(name, str) or not isinstance(enabled, bool):
            raise refuse("invalid_step", number=number)
        domain = name.split(".", 1)[0]
        if domain in ALLOWED_DOMAINS:
            if entry.get("action", "run") != "run" or any(entry.get(key) is not None for key in STEP_SETTINGS):
                raise refuse("invalid_step", number=number)
            if name not in old_items and not item_is_allowed(hass, name):
                raise refuse("item_not_allowed", item=name)
            if name in seen:
                raise refuse("duplicate_item", item=name)
            # A script, scene or automation is always known by its item, so it has no id.
            extra: dict[str, Any] = {}
        elif domain in DEVICE_DOMAINS:
            extra = _device_fields(hass, entry, number, existing, claimed | keys)
        else:
            raise refuse("item_not_allowed", item=name)
        if type(offset) is not int or not MIN_OFFSET_MINUTES <= offset <= MAX_OFFSET_MINUTES:
            raise refuse(
                "offset_out_of_range", item=name, low=str(MIN_OFFSET_MINUTES), high=str(MAX_OFFSET_MINUTES)
            )
        step = Step(name, offset, enabled, **extra)
        if step.key in keys:
            raise refuse("invalid_step", number=number)
        seen.add(name)
        keys.add(step.key)
        steps.append(step)
    return steps


def _is_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _device_fields(
    hass: HomeAssistant, entry: dict, number: str, existing: Sequence[Step], taken: set[str]
) -> dict[str, Any]:
    name, action, step_id = entry["item"], entry.get("action"), entry.get("id") or ""
    if not isinstance(action, str) or not isinstance(step_id, str) or len(step_id) > MAX_ID_LENGTH:
        raise refuse("invalid_step", number=number)
    settings = {key: entry.get(key) for key in STEP_SETTINGS}
    if any(value is not None and not _is_number(value) for value in settings.values()):
        raise refuse("invalid_step", number=number)
    if not step_id:
        # A list sent without ids keeps the ids it had, so a step that already ran isn't seen as new.
        step_id = next(
            (
                step.id
                for step in existing
                if step.id and step.id not in taken and (step.item, step.action) == (name, action)
            ),
            uuid4().hex[:12],
        )
    old = next((step for step in existing if step.key == step_id), None)
    unchanged = (
        old is not None
        and (old.item, old.action) == (name, action)
        and all(getattr(old, key) == value for key, value in settings.items())
    )
    if not unchanged:
        _check_device(hass, name, action, settings, number)
    return {"id": step_id, "action": action, **settings}


def _check_device(hass: HomeAssistant, name: str, action: str, settings: dict[str, Any], number: str) -> None:
    info = device_info(hass, name)
    if info is None:
        raise refuse("item_not_allowed", item=name)
    if action not in info["actions"]:
        raise refuse("action_not_offered", item=name)
    allowed: set[str] = set()
    if action == "turn_on" and info.get("brightness"):
        allowed = {"brightness"}
    elif action == "turn_on" and info.get("temperature"):
        allowed = {"temperature"}
    elif action == "set_temperature":
        allowed = {"heat_to", "cool_to"}
    if any(value is not None and key not in allowed for key, value in settings.items()):
        raise refuse("invalid_step", number=number)
    brightness = settings["brightness"]
    if brightness is not None and (type(brightness) is not int or not 1 <= brightness <= 100):
        raise refuse("brightness_out_of_range")
    low, high = info.get("min_temp"), info.get("max_temp")
    for key in ("temperature", "heat_to", "cool_to"):
        value = settings[key]
        if value is None:
            continue
        if (low is not None and value < low) or (high is not None and value > high):
            raise refuse("temperature_out_of_range", item=name, low=_plain(low), high=_plain(high))
    if action == "set_temperature":
        if settings["heat_to"] is None or settings["cool_to"] is None:
            raise refuse("invalid_step", number=number)
        if settings["heat_to"] >= settings["cool_to"]:
            raise refuse("heat_not_below_cool")


def _plain(number: float | None) -> str:
    return "" if number is None else f"{number:g}"
