import json
from datetime import datetime, timedelta, timezone

from rules import (
    Alarm,
    IgnoredEntry,
    IgnoreReason,
    RoutineState,
    Step,
    state_from_dict,
    state_to_dict,
    steps_from_list,
    steps_to_list,
)

NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)


def through_json(state: RoutineState) -> RoutineState:
    return state_from_dict(json.loads(json.dumps(state_to_dict(state))))


def full_state() -> RoutineState:
    first = Alarm(
        time=NOW + timedelta(hours=7),
        latest=NOW + timedelta(hours=7, minutes=10),
        went_off=True,
        cancelled=False,
        skipped=True,
        seen_late=True,
        ran={"script.b", "script.a"},
        dropped={"scene.dim", "automation.fan"},
    )
    second = Alarm(time=NOW + timedelta(hours=9), latest=NOW + timedelta(hours=9), cancelled=True)
    return RoutineState(
        alarms=[first, second],
        current=second,
        skip_next=True,
        last_location="home",
        last_ignored=IgnoredEntry(
            time=NOW + timedelta(hours=8, seconds=3),
            package="com.example.routines",
            reason=IgnoreReason.WRONG_APP,
        ),
    )


def test_state_survives_a_round_through_json():
    state = full_state()
    loaded = through_json(state)
    assert loaded == state
    assert loaded.current is loaded.alarms[1]


def test_seen_late_and_dropped_survive_a_restart():
    loaded = through_json(full_state())
    assert loaded.alarms[0].seen_late is True
    assert loaded.alarms[0].dropped == {"scene.dim", "automation.fan"}
    assert loaded.alarms[1].seen_late is False
    assert loaded.alarms[1].dropped == set()


def test_sets_are_saved_as_sorted_lists():
    saved = state_to_dict(full_state())["alarms"][0]
    assert saved["ran"] == ["script.a", "script.b"]
    assert saved["dropped"] == ["automation.fan", "scene.dim"]


def test_times_are_saved_as_iso_strings():
    saved = state_to_dict(full_state())
    assert saved["alarms"][0]["time"] == "2026-11-02T07:00:00+00:00"
    assert saved["last_ignored"]["time"] == "2026-11-02T08:00:03+00:00"


def test_current_is_saved_as_an_index():
    assert state_to_dict(full_state())["current"] == 1


def test_current_none_round_trips():
    state = full_state()
    state.current = None
    assert through_json(state).current is None


def test_empty_state_round_trip():
    loaded = through_json(RoutineState())
    assert loaded == RoutineState()
    assert loaded.current is None
    assert loaded.last_ignored is None


def test_ignored_entry_without_a_package():
    state = RoutineState(
        last_ignored=IgnoredEntry(time=NOW, package=None, reason=IgnoreReason.NO_CLOCK)
    )
    assert through_json(state).last_ignored == state.last_ignored


def test_steps_round_trip_through_json():
    steps = [Step("script.heater", -30), Step("scene.lights", 0, enabled=False)]
    assert steps_from_list(json.loads(json.dumps(steps_to_list(steps)))) == steps


def test_no_steps_round_trip():
    assert steps_from_list(steps_to_list([])) == []
