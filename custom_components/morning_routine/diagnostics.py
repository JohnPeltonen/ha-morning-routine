"""What the routine knows, for the Download diagnostics button."""

from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.morning_routine import RoutineConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: RoutineConfigEntry) -> dict[str, Any]:
    routine = entry.runtime_data
    data = routine.snapshot()
    # The saved location can be the name of a zone. These files get attached to public bug reports,
    # and the home check only needs home or not home.
    state = data["state"]
    if state["last_location"] is not None:
        state["last_location"] = "home" if state["last_location"] == "home" else "not_home"
    return {"last_result": routine.last_result, **data}
