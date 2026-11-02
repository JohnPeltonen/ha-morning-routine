"""What the routine knows, for the Download diagnostics button."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import RoutineConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: RoutineConfigEntry) -> dict[str, Any]:
    routine = entry.runtime_data
    return {"last_result": routine.last_result, **routine.snapshot()}
