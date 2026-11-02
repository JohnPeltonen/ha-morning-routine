"""Shared constants and helpers for the Home Assistant tests."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

START = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)
ALARM = START + timedelta(hours=2)


@dataclass(frozen=True)
class Phone:
    device_id: str
    sensor_id: str
    tracker_id: str


def entity_id(hass: HomeAssistant, entry, platform: str, key: str) -> str:
    found = er.async_get(hass).async_get_entity_id(platform, "morning_routine", f"{entry.entry_id}_{key}")
    assert found is not None, f"no {platform} entity with key {key}"
    return found


def at(time: datetime, **offset: float) -> datetime:
    return time + timedelta(**offset)


async def advance(hass: HomeAssistant, freezer, when: datetime) -> None:
    """Move the clock to `when`, fire the timers due by then, and let everything settle."""
    freezer.move_to(when)
    async_fire_time_changed_exact(hass, when)
    await hass.async_block_till_done()


async def advance_without_waiting(hass: HomeAssistant, freezer, when: datetime) -> None:
    """Like advance, but for tests where a step is held open and block_till_done would wait for it."""
    freezer.move_to(when)
    async_fire_time_changed_exact(hass, when)
    await let_loop_run()


async def let_loop_run() -> None:
    for _ in range(50):
        await asyncio.sleep(0)
