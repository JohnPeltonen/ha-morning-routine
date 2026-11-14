"""Lights and thermostats as steps: what type a device is, and what a step sends to it."""

import math
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.morning_routine.rules import Step

# Home Assistant's climate feature numbers. Written out so this integration doesn't depend on climate.
TARGET_TEMPERATURE = 1
TARGET_TEMPERATURE_RANGE = 2
TURN_OFF = 128
TURN_ON = 256

# The words the card shows. The card holds none of its own for what a device can do.
ACTION_NAMES = {"run": "Run", "turn_on": "Turn on", "turn_off": "Turn off", "set_temperature": "Set temperatures"}
SETTING_NAMES = {"brightness": "Brightness", "temperature": "Temperature", "heat_to": "Heat to", "cool_to": "Cool to"}
# What happens when an optional setting is left out.
SETTING_HINTS = {"brightness": "as it was", "temperature": "last setting"}
# What a script, scene or automation can do.
RUN_ACTIONS: list[dict[str, Any]] = [{"action": "run", "name": ACTION_NAMES["run"], "settings": []}]


def describe_device(hass: HomeAssistant, entity_id: str) -> list[dict[str, Any]] | None:
    """The actions a step can take on this light or thermostat, each with its settings.

    None when it can't be offered right now. A setting's `selector` is in Home Assistant's
    selector format, so the card can draw it and the checks can read its limits.
    """
    state = hass.states.get(entity_id)
    if state is None or state.state == STATE_UNAVAILABLE:
        return None
    domain = entity_id.split(".", 1)[0]
    attributes = state.attributes
    if domain == "light":
        modes = attributes.get("supported_color_modes") or []
        dims = any(mode != "onoff" for mode in modes)
        return [_action("turn_on", [_brightness(attributes)] if dims else []), _action("turn_off")]
    if domain != "climate":
        return None

    features = attributes.get("supported_features") or 0
    unit = hass.config.units.temperature_unit
    fahrenheit = unit == UnitOfTemperature.FAHRENHEIT
    low, high = attributes.get("min_temp"), attributes.get("max_temp")
    if not (_is_number(low) and _is_number(high)):
        # Home Assistant's own limits for a thermostat that reports none.
        low, high = (45, 95) if fahrenheit else (7, 35)
    step = attributes.get("target_temp_step")
    if not (_is_number(step) and step > 0):
        step = 1 if fahrenheit else 0.5
    selector = {"number": {"min": low, "max": high, "step": step, "mode": "slider", "unit_of_measurement": unit}}

    if features & TARGET_TEMPERATURE_RANGE:
        heat, cool = attributes.get("target_temp_low"), attributes.get("target_temp_high")
        if not (_is_number(heat) and _is_number(cool) and low <= heat < cool <= high):
            # A third and two thirds of the way up, so a new step can be saved without moving either.
            third = (high - low) / 3
            heat, cool = _on_a_step(low + third, low, step), _on_a_step(low + 2 * third, low, step)
        return [
            _action(
                "set_temperature",
                [_setting("heat_to", False, heat, selector), _setting("cool_to", False, cool, selector)],
            )
        ]
    actions = [
        action for action, feature in (("turn_on", TURN_ON), ("turn_off", TURN_OFF)) if features & feature
    ]
    if not actions:
        return None
    settings = []
    if features & TARGET_TEMPERATURE:
        current = attributes.get("temperature")
        if not (_is_number(current) and low <= current <= high):
            current = _on_a_step((low + high) / 2, low, step)
        settings = [_setting("temperature", True, current, selector)]
    return [_action(action, settings if action == "turn_on" else []) for action in actions]


def step_detail(hass: HomeAssistant, step: Step) -> str:
    """What a light or thermostat step does, in words. Empty for a script, scene or automation."""
    unit = hass.config.units.temperature_unit
    if step.action == "turn_off":
        return "Turn off"
    if step.action == "turn_on":
        if step.brightness is not None:
            return f"Turn on at {step.brightness:g}%"
        if step.temperature is not None:
            return f"Turn on at {step.temperature:g}{unit}"
        return "Turn on"
    if step.action == "set_temperature":
        return f"Heat to {step.heat_to:g}{unit}, cool to {step.cool_to:g}{unit}"
    return ""


def _is_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _on_a_step(value: float, low: float, step: float) -> float:
    """The slider position nearest to a value."""
    snapped = low + round((value - low) / step) * step
    return int(snapped) if snapped == int(snapped) else snapped


def _action(action: str, settings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"action": action, "name": ACTION_NAMES[action], "settings": settings or []}


def _setting(key: str, optional: bool, start: float, selector: dict[str, Any]) -> dict[str, Any]:
    setting = {"key": key, "name": SETTING_NAMES[key], "optional": optional, "start": start, "selector": selector}
    if optional:
        setting["hint"] = SETTING_HINTS[key]
    return setting


def _brightness(attributes: Any) -> dict[str, Any]:
    # A light reports its brightness from 0 to 255. A step takes a percent.
    current = attributes.get("brightness")
    start = min(100, max(1, round(current / 255 * 100))) if _is_number(current) else 100
    selector = {"number": {"min": 1, "max": 100, "step": 1, "mode": "slider", "unit_of_measurement": "%"}}
    return _setting("brightness", True, start, selector)


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
    if state.state == "cool":
        return {"temperature": step.cool_to}
    if state.state == "heat":
        return {"temperature": step.heat_to}
    if state.state == "heat_cool" or shows_range:
        return {"target_temp_low": step.heat_to, "target_temp_high": step.cool_to}
    if state.state == "auto":
        return {"temperature": step.heat_to}
    raise HomeAssistantError(f"{step.item} is in {state.state} mode, which takes no temperature")
