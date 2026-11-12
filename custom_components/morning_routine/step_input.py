"""Checks a list of steps that came from a person."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.morning_routine.const import DOMAIN, MAX_OFFSET_MINUTES, MIN_OFFSET_MINUTES
from custom_components.morning_routine.routine import item_is_allowed
from custom_components.morning_routine.rules import Step

STEP_KEYS = {"item", "offset_minutes", "enabled"}


def refuse(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders)


def parse_steps(hass: HomeAssistant, raw: Any, keep: frozenset[str] = frozenset()) -> list[Step]:
    """Check the whole list, so a refused call changes nothing.

    `keep` is the items already in the routine. One that lost its label may stay, so the
    other steps can still be changed.
    """
    if not isinstance(raw, list):
        raise refuse("steps_not_a_list")
    steps: list[Step] = []
    seen: set[str] = set()
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict) or not {"item", "offset_minutes"} <= item.keys() <= STEP_KEYS:
            raise refuse("invalid_step", number=str(index))
        name, offset, enabled = item["item"], item["offset_minutes"], item.get("enabled", True)
        if not isinstance(name, str) or not isinstance(enabled, bool):
            raise refuse("invalid_step", number=str(index))
        if name not in keep and not item_is_allowed(hass, name):
            raise refuse("item_not_allowed", item=name)
        if name in seen:
            raise refuse("duplicate_item", item=name)
        if type(offset) is not int or not MIN_OFFSET_MINUTES <= offset <= MAX_OFFSET_MINUTES:
            raise refuse(
                "offset_out_of_range", item=name, low=str(MIN_OFFSET_MINUTES), high=str(MAX_OFFSET_MINUTES)
            )
        seen.add(name)
        steps.append(Step(name, offset, enabled))
    return steps
