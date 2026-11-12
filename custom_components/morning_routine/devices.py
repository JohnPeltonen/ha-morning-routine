"""Lights and thermostats as steps: what type a device is, and what a step sends to it."""

from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.morning_routine.rules import Step

# Home Assistant's climate feature numbers. Written out so this integration doesn't depend on climate.
TARGET_TEMPERATURE = 1
TARGET_TEMPERATURE_RANGE = 2
TURN_OFF = 128
TURN_ON = 256


def device_info(hass: HomeAssistant, entity_id: str) -> dict[str, Any] | None:
    """What the card may offer for this device. None when it can't be offered right now."""
    state = hass.states.get(entity_id)
    if state is None or state.state == STATE_UNAVAILABLE:
        return None
    domain = entity_id.split(".", 1)[0]
    attributes = state.attributes
    if domain == "light":
        modes = attributes.get("supported_color_modes") or []
        return {
            "type": "light",
            "actions": ["turn_on", "turn_off"],
            "brightness": any(mode != "onoff" for mode in modes),
        }
    if domain != "climate":
        return None
    features = attributes.get("supported_features") or 0
    limits = {"min_temp": attributes.get("min_temp"), "max_temp": attributes.get("max_temp")}
    if features & TARGET_TEMPERATURE_RANGE:
        return {"type": "thermostat_range", "actions": ["set_temperature"], **limits}
    actions = [
        action for action, feature in (("turn_on", TURN_ON), ("turn_off", TURN_OFF)) if features & feature
    ]
    if not actions:
        return None
    return {
        "type": "thermostat",
        "actions": actions,
        "temperature": bool(features & TARGET_TEMPERATURE),
        **limits,
    }


def device_calls(hass: HomeAssistant, step: Step) -> list[tuple[str, str, dict[str, Any]]]:
    """The Home Assistant actions a device step sends, in order."""
    target = {"entity_id": step.item}
    domain = step.item.split(".", 1)[0]
    if step.action == "turn_off":
        return [(domain, "turn_off", target)]
    if step.action == "turn_on" and domain == "light":
        if step.brightness is None:
            return [("light", "turn_on", target)]
        return [("light", "turn_on", {**target, "brightness_pct": step.brightness})]
    if step.action == "turn_on":
        calls: list[tuple[str, str, dict[str, Any]]] = [("climate", "turn_on", target)]
        if step.temperature is not None:
            calls.append(("climate", "set_temperature", {**target, "temperature": step.temperature}))
        return calls
    if step.action == "set_temperature":
        return [("climate", "set_temperature", {**target, **_range_settings(hass, step)})]
    raise HomeAssistantError(f"A step can't {step.action} {step.item}")


def _range_settings(hass: HomeAssistant, step: Step) -> dict[str, float | None]:
    """The numbers that fit the thermostat's mode right now. A step never changes the mode."""
    state = hass.states.get(step.item)
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        raise HomeAssistantError(f"{step.item} isn't responding, so its temperatures weren't set")
    if state.state == "off":
        raise HomeAssistantError(f"{step.item} is off, so its temperatures weren't set")
    shows_range = (
        state.attributes.get("target_temp_low") is not None
        and state.attributes.get("target_temp_high") is not None
    )
    if state.state == "heat_cool" or shows_range:
        return {"target_temp_low": step.heat_to, "target_temp_high": step.cool_to}
    if state.state == "cool":
        return {"temperature": step.cool_to}
    if state.state in ("heat", "auto"):
        return {"temperature": step.heat_to}
    raise HomeAssistantError(f"{step.item} is in {state.state} mode, which takes no temperature")
