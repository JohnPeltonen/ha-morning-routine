from datetime import datetime, timezone

from rules import IgnoreReason, RoutineState, Step, observe_entry, observe_no_alarm, steps_to_run

DESK_CLOCK = "com.google.android.deskclock"
SAMSUNG_CLOCK = "com.sec.android.app.clockpackage"
ROUTINES = "com.samsung.android.app.routines"
NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)

HEATER = Step("script.heater", -30)


def at(hms: str) -> datetime:
    hour, minute, second = (int(part) for part in hms.split(":"))
    return NOW.replace(hour=hour, minute=minute, second=second)


def replay(state: RoutineState, clock: str, entries: list[tuple[str, str, str]]) -> None:
    """Each entry is (arrived at, entry time, package)."""
    for arrived, entry, package in entries:
        observe_entry(state, at(entry), package, clock, True, at(arrived))


def run(state: RoutineState, steps: list[Step], now: str) -> list[str]:
    return [step.item for _, step in steps_to_run(state, steps, True, at(now))]


FIRST_PHONE_MORNING = [
    ("00:00:10", "00:41:50", ROUTINES),
    ("00:41:51", "07:00:03", SAMSUNG_CLOCK),
    ("07:00:04", "07:30:00", ROUTINES),
    ("07:30:01", "07:30:05", ROUTINES),
    ("07:30:05", "09:00:00", DESK_CLOCK),
]


def test_first_phone_runs_once_for_the_0900_alarm():
    state = RoutineState(last_location="home")
    replay(state, DESK_CLOCK, FIRST_PHONE_MORNING)
    assert len(state.alarms) == 1
    alarm = state.current
    assert alarm.time == at("09:00:00")

    assert run(state, [HEATER], "08:29:59") == []
    assert run(state, [HEATER], "08:30:00") == ["script.heater"]
    alarm.ran.add("script.heater")
    assert run(state, [HEATER], "08:30:01") == []
    assert run(state, [HEATER], "09:00:00") == []

    replay(state, DESK_CLOCK, [("09:00:01", "21:00:00", ROUTINES)])
    assert state.current is alarm
    assert run(state, [HEATER], "09:00:02") == []
    assert state.alarms == [alarm]


def test_first_phone_hidden_alarm_runs_when_it_appears():
    state = RoutineState(last_location="home")
    replay(state, DESK_CLOCK, FIRST_PHONE_MORNING[:-1])
    assert state.alarms == []
    assert run(state, [HEATER], "07:30:04") == []

    replay(state, DESK_CLOCK, FIRST_PHONE_MORNING[-1:])
    assert run(state, [HEATER], "07:30:05") == []
    assert run(state, [HEATER], "08:29:59") == []
    assert run(state, [HEATER], "08:30:00") == ["script.heater"]


def test_first_phone_hidden_alarm_with_more_notice_than_it_left_runs_at_once():
    state = RoutineState(last_location="home")
    replay(state, DESK_CLOCK, FIRST_PHONE_MORNING)
    early = Step("script.early", -120)
    assert run(state, [early], "07:30:05") == ["script.early"]


def test_second_phone_moved_alarm_uses_new_time():
    state = RoutineState(last_location="home")
    replay(
        state,
        SAMSUNG_CLOCK,
        [
            ("05:00:00", "06:42:00", SAMSUNG_CLOCK),
            ("06:00:00", "09:03:00", SAMSUNG_CLOCK),
        ],
    )
    assert state.current.time == at("09:03:00")
    assert run(state, [HEATER], "06:12:00") == []
    assert run(state, [HEATER], "08:32:59") == []
    assert run(state, [HEATER], "08:33:00") == ["script.heater"]
    assert state.alarms == [state.current]


def test_second_phone_probable_snooze_runs_nothing_again():
    state = RoutineState(last_location="home")
    replay(state, SAMSUNG_CLOCK, [("08:00:00", "09:03:00", SAMSUNG_CLOCK)])
    alarm = state.current
    assert run(state, [HEATER], "08:33:00") == ["script.heater"]
    alarm.ran.add("script.heater")

    replay(state, SAMSUNG_CLOCK, [("09:03:01", "09:08:00", SAMSUNG_CLOCK)])
    observe_no_alarm(state, at("09:03:12"))
    assert state.current is alarm
    assert state.alarms == [alarm]
    assert alarm.time == at("09:03:00")
    assert not alarm.cancelled
    assert run(state, [HEATER], "09:03:12") == []
    assert run(state, [HEATER], "09:08:00") == []


def test_short_blip_keeps_the_alarm():
    state = RoutineState(last_location="home")
    replay(state, SAMSUNG_CLOCK, [("08:00:00", "09:03:00", SAMSUNG_CLOCK)])
    alarm = state.current
    assert run(state, [HEATER], "08:33:00") == ["script.heater"]
    alarm.ran.add("script.heater")

    # An unknown or short unavailable reading calls nothing, then the same value comes back.
    replay(state, SAMSUNG_CLOCK, [("08:33:30", "09:03:00", SAMSUNG_CLOCK)])
    assert state.current is alarm
    assert state.alarms == [alarm]
    assert alarm.ran == {"script.heater"}
    assert run(state, [HEATER], "08:34:00") == []


def test_no_samsung_clock_false_entry_runs():
    state = RoutineState(last_location="home")
    replay(
        state,
        DESK_CLOCK,
        [
            ("21:00:00", "22:30:03", SAMSUNG_CLOCK),
            ("06:00:00", "07:00:03", SAMSUNG_CLOCK),
        ],
    )
    assert state.alarms == []
    assert state.current is None
    assert state.last_ignored.reason is IgnoreReason.WRONG_APP
    for now in ("06:30:00", "07:00:03", "21:30:00", "22:30:03"):
        assert run(state, [HEATER, Step("script.at", 0)], now) == []

    other = RoutineState(last_location="home")
    replay(other, SAMSUNG_CLOCK, [("06:00:00", "07:00:03", SAMSUNG_CLOCK)])
    assert other.alarms == []
    assert other.last_ignored.reason is IgnoreReason.NOT_ON_THE_MINUTE
    assert run(other, [HEATER], "06:30:00") == []
