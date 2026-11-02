"""Shared constants and helpers for the Home Assistant tests."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

START = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)
ALARM = START + timedelta(hours=2)


@dataclass(frozen=True)
class Phone:
    device_id: str
    sensor_id: str
    tracker_id: str


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
