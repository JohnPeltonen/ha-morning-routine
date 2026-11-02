"""Alarm decisions for the morning routine. Must never import homeassistant."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

SAME_ALARM_GAP = timedelta(minutes=20)
NO_ALARM_AFTER = timedelta(seconds=60)
CLOCK_SKEW = timedelta(seconds=5)
RECORD_KEPT = timedelta(minutes=90)


class IgnoreReason(StrEnum):
    NO_CLOCK = "no_clock"
    WRONG_APP = "wrong_app"
    NOT_ON_THE_MINUTE = "not_on_the_minute"
    IN_THE_PAST = "in_the_past"


@dataclass
class Alarm:
    time: datetime
    latest: datetime
    went_off: bool = False
    cancelled: bool = False
    skipped: bool = False
    seen_late: bool = False
    ran: set[str] = field(default_factory=set)
    dropped: set[str] = field(default_factory=set)


@dataclass
class IgnoredEntry:
    time: datetime
    package: str | None
    reason: IgnoreReason


@dataclass
class RoutineState:
    alarms: list[Alarm] = field(default_factory=list)
    current: Alarm | None = None
    skip_next: bool = False
    last_location: str | None = None
    last_ignored: IgnoredEntry | None = None


def check_entry(
    time: datetime,
    package: str | None,
    clock: str | None,
    require_zero_seconds: bool,
    now: datetime,
) -> IgnoreReason | None:
    if clock is None:
        return IgnoreReason.NO_CLOCK
    if package != clock:
        return IgnoreReason.WRONG_APP
    if require_zero_seconds and time.second != 0:
        return IgnoreReason.NOT_ON_THE_MINUTE
    if time < now - RECORD_KEPT:
        return IgnoreReason.IN_THE_PAST
    return None


def settle(state: RoutineState, now: datetime) -> None:
    current = state.current
    if current is not None and not current.went_off and now >= current.time - CLOCK_SKEW:
        current.went_off = True
        if state.skip_next:
            current.skipped = True
            state.skip_next = False
    state.alarms = [alarm for alarm in state.alarms if now <= alarm.time + RECORD_KEPT]
    if current is not None and not any(alarm is current for alarm in state.alarms):
        state.current = None


def _cancel_current(state: RoutineState) -> None:
    if state.current is not None:
        state.current.cancelled = True
        state.current = None


def observe_entry(
    state: RoutineState,
    time: datetime,
    package: str | None,
    clock: str | None,
    require_zero_seconds: bool,
    now: datetime,
) -> None:
    settle(state, now)
    reason = check_entry(time, package, clock, require_zero_seconds, now)
    current = state.current

    if reason is not None:
        state.last_ignored = IgnoredEntry(time=time, package=package, reason=reason)
        if (
            reason is not IgnoreReason.IN_THE_PAST
            and current is not None
            and not current.went_off
            and time > current.time
        ):
            _cancel_current(state)
        return

    if current is not None:
        if time == current.latest or time == current.time:
            return
        if current.latest < time <= current.latest + SAME_ALARM_GAP:
            current.latest = time
            if not current.went_off:
                current.time = time
            return

    for alarm in state.alarms:
        if time == alarm.time or time == alarm.latest:
            alarm.cancelled = False
            state.current = alarm
            break
    else:
        alarm = Alarm(time=time, latest=time)
        state.alarms.append(alarm)
        state.current = alarm
    if not alarm.went_off and now > alarm.time + CLOCK_SKEW:
        alarm.went_off = True
        alarm.seen_late = True
    settle(state, now)


def observe_no_alarm(state: RoutineState, now: datetime) -> None:
    settle(state, now)
    if state.current is not None and not state.current.went_off:
        _cancel_current(state)


def change_clock(state: RoutineState) -> None:
    state.current = None
