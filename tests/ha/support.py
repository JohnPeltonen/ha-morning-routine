"""Shared constants and helpers for the Home Assistant tests."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed_exact

START = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)
ALARM = START + timedelta(hours=2)
SENSOR_NAME = "sensor.test_phone_next_alarm"
TRACKER_NAME = "device_tracker.test_phone"


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
