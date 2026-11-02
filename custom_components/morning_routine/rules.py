"""Alarm decisions for the morning routine. Must never import homeassistant."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

SAME_ALARM_GAP = timedelta(minutes=20)
NO_ALARM_AFTER = timedelta(seconds=60)
CLOCK_SKEW = timedelta(seconds=5)
RECORD_KEPT = timedelta(minutes=90)
ON_TIME_GRACE = timedelta(seconds=10)
LATE_LIMIT = timedelta(minutes=5)


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


@dataclass(frozen=True)
class Step:
    item: str
    offset_minutes: int
    enabled: bool = True


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


def is_home(state: RoutineState) -> bool:
    return state.last_location == "home"


def _could_run_steps(state: RoutineState, alarm: Alarm) -> bool:
    if alarm.skipped:
        return False
    return alarm.went_off or (alarm is state.current and not alarm.cancelled)


def steps_to_run(
    state: RoutineState,
    steps: list[Step],
    routine_on: bool,
    now: datetime,
) -> list[tuple[Alarm, Step]]:
    settle(state, now)
    due: list[tuple[Alarm, Step]] = []
    for alarm in state.alarms:
        if not _could_run_steps(state, alarm):
            continue
        blocked = not routine_on or not is_home(state) or (state.skip_next and not alarm.went_off)
        for step in steps:
            if step.item in alarm.ran or step.item in alarm.dropped:
                continue
            if alarm.seen_late:
                alarm.dropped.add(step.item)
                continue
            run_at = alarm.time + timedelta(minutes=step.offset_minutes)
            if run_at > now:
                continue
            if now >= alarm.time and now - run_at > ON_TIME_GRACE:
                alarm.dropped.add(step.item)
            elif step.enabled and not blocked:
                due.append((alarm, step))
    return due


def steps_after_restart(
    state: RoutineState,
    steps: list[Step],
    routine_on: bool,
    now: datetime,
) -> list[tuple[Alarm, Step]]:
    settle(state, now)
    due: list[tuple[Alarm, Step]] = []
    for alarm in state.alarms:
        if not _could_run_steps(state, alarm):
            continue
        blocked = (
            not routine_on
            or not is_home(state)
            or (state.skip_next and (not alarm.went_off or alarm.seen_late))
        )
        for step in steps:
            if step.item in alarm.ran or step.item in alarm.dropped:
                continue
            late = now - (alarm.time + timedelta(minutes=step.offset_minutes))
            if late < timedelta(0):
                continue
            if blocked or not step.enabled or late >= LATE_LIMIT:
                alarm.dropped.add(step.item)
            else:
                due.append((alarm, step))
    return due


def next_wakeup(state: RoutineState, steps: list[Step], now: datetime) -> datetime | None:
    times: list[datetime] = []
    current = state.current
    if current is not None and not current.went_off:
        times.append(current.time - CLOCK_SKEW)
    for alarm in state.alarms:
        times.append(alarm.time + RECORD_KEPT)
        if alarm.seen_late or not _could_run_steps(state, alarm):
            continue
        for step in steps:
            if step.enabled:
                times.append(alarm.time + timedelta(minutes=step.offset_minutes))
    future = [time for time in times if time > now]
    return min(future) if future else None


def set_skip(state: RoutineState, on: bool, now: datetime) -> None:
    settle(state, now)
    state.skip_next = on
