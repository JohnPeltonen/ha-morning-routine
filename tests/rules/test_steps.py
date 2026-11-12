from datetime import datetime, timezone

from rules import (
    ON_TIME_GRACE,
    RoutineState,
    Step,
    is_home,
    next_wakeup,
    observe_entry,
    observe_no_alarm,
    set_skip,
    settle,
    steps_after_restart,
    steps_to_run,
)

CLOCK = "com.sec.android.app.clockpackage"
NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)

HEATER = Step("script.heater", -30)


def at(hms: str) -> datetime:
    hour, minute, second = (int(part) for part in hms.split(":"))
    return NOW.replace(hour=hour, minute=minute, second=second)


def enter(state: RoutineState, entry: str, now: str, package: str = CLOCK) -> None:
    observe_entry(state, at(entry), package, CLOCK, True, at(now))


def home_state(entry: str = "07:00:00", now: str = "06:00:00") -> RoutineState:
    state = RoutineState(last_location="home")
    enter(state, entry, now)
    return state


def run(
    state: RoutineState,
    steps: list[Step],
    now: str,
    routine_on: bool = True,
) -> list[str]:
    return [step.item for _, step in steps_to_run(state, steps, routine_on, at(now))]


def restart(
    state: RoutineState,
    steps: list[Step],
    now: str,
    routine_on: bool = True,
) -> list[str]:
    return [step.item for _, step in steps_after_restart(state, steps, routine_on, at(now))]


def test_is_home_only_for_home():
    assert is_home(RoutineState(last_location="home"))
    assert not is_home(RoutineState(last_location="not_home"))
    assert not is_home(RoutineState(last_location="work"))
    assert not is_home(RoutineState())


def test_not_due_before_its_time():
    state = home_state()
    assert run(state, [HEATER], "06:29:59") == []


def test_due_at_its_time():
    state = home_state()
    result = steps_to_run(state, [HEATER], True, at("06:30:00"))
    assert result == [(state.current, HEATER)]


def test_after_ran_it_doesnt_run_again():
    state = home_state()
    assert run(state, [HEATER], "06:30:00") == ["script.heater"]
    state.current.ran.add("script.heater")
    assert run(state, [HEATER], "06:30:01") == []
    assert run(state, [HEATER], "06:45:00") == []


def test_steps_to_run_doesnt_change_ran():
    state = home_state()
    run(state, [HEATER], "06:30:00")
    assert state.current.ran == set()


def test_alarm_seen_late_runs_right_away():
    state = home_state(now="06:45:00")
    assert not state.current.seen_late
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_alarm_seen_after_it_passed_runs_nothing():
    state = RoutineState(last_location="home")
    enter(state, "07:00:00", "07:10:05")
    assert run(state, [HEATER], "07:10:05") == []
    assert run(state, [HEATER], "07:10:06") == []


def test_seen_late_alarm_runs_nothing_even_inside_the_grace():
    state = RoutineState(last_location="home")
    enter(state, "07:00:00", "07:10:05")
    assert state.current.seen_late
    after = Step("script.after", 10)
    assert run(state, [after], "07:10:05") == []


def test_at_alarm_step_runs_on_time():
    state = home_state()
    step = Step("script.at", 0)
    assert run(state, [step], "06:59:59") == []
    assert run(state, [step], "07:00:00") == ["script.at"]


def test_after_alarm_step_runs_on_time():
    state = home_state()
    step = Step("script.after", 10)
    assert run(state, [step], "07:09:59") == []
    assert run(state, [step], "07:10:00") == ["script.after"]


def test_after_alarm_step_blocked_at_its_time_is_lost():
    state = home_state()
    state.last_location = "not_home"
    step = Step("script.after", 10)
    assert run(state, [step], "07:10:00") == []
    state.last_location = "home"
    assert run(state, [step], "07:12:00") == []


def test_grace_boundary():
    step = Step("script.after", 10)
    assert ON_TIME_GRACE.total_seconds() == 10
    assert run(home_state(), [step], "07:10:10") == ["script.after"]
    assert run(home_state(), [step], "07:10:11") == []


def test_routine_turned_on_catches_up():
    state = home_state()
    assert run(state, [HEATER], "06:30:00", routine_on=False) == []
    assert run(state, [HEATER], "06:45:00", routine_on=True) == ["script.heater"]


def test_step_toggle_turned_on_catches_up():
    state = home_state()
    off = Step("script.heater", -30, enabled=False)
    on = Step("script.heater", -30, enabled=True)
    assert run(state, [off], "06:30:00") == []
    assert run(state, [on], "06:45:00") == ["script.heater"]


def test_skip_turned_off_catches_up():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    assert run(state, [HEATER], "06:30:00") == []
    set_skip(state, False, at("06:45:00"))
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_phone_coming_home_catches_up():
    state = home_state()
    state.last_location = "not_home"
    assert run(state, [HEATER], "06:30:00") == []
    state.last_location = "home"
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_step_added_with_passed_time_catches_up():
    state = home_state()
    assert run(state, [], "06:45:00") == []
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_step_retimed_to_passed_time_catches_up():
    state = home_state()
    later = Step("script.heater", -10)
    assert run(state, [later], "06:45:00") == []
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_clock_chosen_catches_up():
    state = RoutineState(last_location="home")
    observe_entry(state, at("07:00:00"), CLOCK, None, True, at("06:30:00"))
    assert run(state, [HEATER], "06:30:00") == []
    observe_entry(state, at("07:00:00"), CLOCK, CLOCK, True, at("06:45:00"))
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_block_cleared_after_alarm_passed_runs_nothing():
    state = home_state()
    assert run(state, [HEATER], "06:30:00", routine_on=False) == []
    assert run(state, [HEATER], "07:01:00", routine_on=True) == []


def test_retimed_step_that_ran_doesnt_run_again():
    state = home_state()
    assert run(state, [HEATER], "06:30:00") == ["script.heater"]
    state.current.ran.add("script.heater")
    retimed = Step("script.heater", -20)
    assert run(state, [retimed], "06:45:00") == []


def test_removed_and_readded_step_that_ran_doesnt_run_again():
    state = home_state()
    state.current.ran.add("script.heater")
    assert run(state, [], "06:40:00") == []
    assert run(state, [HEATER], "06:45:00") == []


def test_retimed_to_later_runs_at_new_time():
    state = home_state()
    later = Step("script.heater", -10)
    assert run(state, [later], "06:49:59") == []
    assert run(state, [later], "06:50:00") == ["script.heater"]


def test_edit_moves_steps_that_havent_run():
    state = home_state()
    enter(state, "07:15:00", "06:20:00")
    assert state.current.time == at("07:15:00")
    assert run(state, [HEATER], "06:30:00") == []
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_away_blocks_every_step():
    state = home_state()
    state.last_location = "not_home"
    steps = [HEATER, Step("script.at", 0), Step("script.after", 10)]
    assert run(state, steps, "06:30:00") == []
    assert run(state, steps, "07:00:00") == []
    assert run(state, steps, "07:10:00") == []


def test_named_zone_blocks():
    state = home_state()
    state.last_location = "work"
    assert run(state, [HEATER], "06:30:00") == []


def test_never_had_a_location_blocks():
    state = home_state()
    state.last_location = None
    assert run(state, [HEATER], "06:30:00") == []


def test_gone_off_alarm_carries_on_after_new_alarm_is_current():
    state = home_state()
    first = state.current
    step = Step("script.after", 10)
    enter(state, "09:00:00", "07:05:00")
    assert state.current is not first
    result = steps_to_run(state, [step], True, at("07:10:00"))
    assert result == [(first, step)]


def test_alarm_behind_an_earlier_alarm_runs_nothing():
    state = RoutineState(last_location="home")
    enter(state, "09:30:00", "06:00:00")
    behind = state.current
    enter(state, "07:00:00", "06:01:00")
    assert state.current is not behind
    step = Step("script.heater", -120)
    assert run(state, [step], "06:00:00") == ["script.heater"]
    state.current.ran.add("script.heater")
    assert run(state, [step], "07:30:00") == []


def test_cancelled_alarm_runs_nothing():
    state = home_state()
    observe_no_alarm(state, at("06:20:00"))
    assert state.alarms[0].cancelled
    assert run(state, [HEATER], "06:30:00") == []


def test_skip_before_alarm_blocks_all_its_steps():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    steps = [HEATER, Step("script.at", 0), Step("script.after", 10)]
    assert run(state, steps, "06:30:00") == []
    assert run(state, steps, "07:00:00") == []
    assert run(state, steps, "07:10:00") == []


def test_skip_used_up_when_alarm_goes_off():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    run(state, [HEATER], "07:00:00")
    assert not state.skip_next
    assert state.current.skipped


def test_skipped_alarm_stays_skipped_through_snooze():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    run(state, [HEATER], "07:00:00")
    alarm = state.current
    enter(state, "07:05:00", "07:00:01")
    assert state.current is alarm
    after = Step("script.after", 10)
    assert run(state, [after], "07:10:00") == []
    assert alarm.skipped


def test_skip_after_alarm_went_off_applies_to_next_alarm():
    state = home_state()
    first = state.current
    after = Step("script.after", 10)
    set_skip(state, True, at("07:01:00"))
    assert state.skip_next
    assert not first.skipped
    assert run(state, [after], "07:10:00") == ["script.after"]
    first.ran.add("script.after")

    enter(state, "08:00:00", "07:20:00")
    second = state.current
    assert second is not first
    assert run(state, [after], "08:10:00") == []
    assert second.skipped
    assert not state.skip_next


def test_skip_with_no_alarm_known_waits_for_next():
    state = RoutineState(last_location="home")
    set_skip(state, True, at("05:00:00"))
    assert state.skip_next
    enter(state, "07:00:00", "06:00:00")
    assert run(state, [HEATER], "06:30:00") == []
    run(state, [HEATER], "07:00:00")
    assert state.current.skipped
    assert not state.skip_next


def test_skip_stays_on_when_alarm_is_cancelled():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    observe_no_alarm(state, at("06:20:00"))
    assert state.current is None
    assert state.skip_next
    enter(state, "08:00:00", "06:30:00")
    run(state, [HEATER], "08:00:00")
    assert state.current.skipped
    assert not state.skip_next


def test_skip_stays_on_when_alarm_is_replaced():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    original = state.current
    enter(state, "06:30:00", "06:10:00")
    replacement = state.current
    assert replacement is not original
    assert state.skip_next
    run(state, [HEATER], "06:30:00")
    assert replacement.skipped
    assert not original.skipped
    assert not state.skip_next


def test_set_skip_settles_first():
    state = home_state()
    alarm = state.current
    set_skip(state, True, at("07:00:30"))
    assert alarm.went_off
    assert not alarm.skipped
    assert state.skip_next


def test_restart_runs_step_under_5_minutes_late():
    state = home_state()
    assert restart(state, [HEATER], "06:34:59") == ["script.heater"]
    assert state.current.dropped == set()
    assert state.current.ran == set()


def test_restart_drops_step_5_minutes_late():
    state = home_state()
    assert restart(state, [HEATER], "06:35:00") == []
    assert state.current.dropped == {"script.heater"}
    assert run(state, [HEATER], "06:45:00") == []


def test_restart_drops_overdue_blocked_step():
    state = home_state()
    state.last_location = "not_home"
    assert restart(state, [HEATER], "06:31:00") == []
    assert state.current.dropped == {"script.heater"}
    state.last_location = "home"
    assert run(state, [HEATER], "06:45:00") == []


def test_restart_drops_overdue_disabled_step():
    state = home_state()
    off = Step("script.heater", -30, enabled=False)
    on = Step("script.heater", -30, enabled=True)
    assert restart(state, [off], "06:31:00") == []
    assert state.current.dropped == {"script.heater"}
    assert run(state, [on], "06:45:00") == []


def test_restart_leaves_future_steps_alone():
    state = home_state()
    assert restart(state, [HEATER], "06:20:00") == []
    assert state.current.dropped == set()
    assert run(state, [HEATER], "06:30:00") == ["script.heater"]


def test_restart_doesnt_repeat_steps_that_ran():
    state = home_state()
    state.current.ran.add("script.heater")
    assert restart(state, [HEATER], "06:31:00") == []
    assert state.current.dropped == set()


def test_restart_runs_seen_late_alarm_step_under_5_minutes():
    state = RoutineState(last_location="home")
    enter(state, "07:00:00", "07:02:00")
    alarm = state.current
    assert alarm.seen_late
    step = Step("script.at", 0)
    assert restart(state, [step], "07:02:00") == ["script.at"]
    assert alarm.dropped == set()


def test_restart_skip_blocks_seen_late_alarm():
    state = RoutineState(last_location="home", skip_next=True)
    enter(state, "07:00:00", "07:02:00")
    alarm = state.current
    assert alarm.seen_late
    step = Step("script.at", 0)
    assert restart(state, [step], "07:02:00") == []
    assert alarm.dropped == {"script.at"}
    assert state.skip_next


def test_restart_leaves_skipped_and_sleeping_alarms_alone():
    state = RoutineState(last_location="home")
    enter(state, "09:30:00", "06:00:00")
    sleeping = state.current
    enter(state, "07:00:00", "06:01:00")
    skipped = state.current
    skipped.skipped = True
    skipped.went_off = True
    step = Step("script.at", -150)
    assert restart(state, [step], "07:00:30") == []
    assert skipped.dropped == set()
    assert sleeping.dropped == set()


def test_next_wakeup_is_soonest_future_time():
    state = home_state()
    steps = [HEATER, Step("script.after", 10)]
    assert next_wakeup(state, steps, at("06:00:00")) == at("06:30:00")
    assert next_wakeup(state, steps, at("06:30:00")) == at("06:59:55")
    settle(state, at("07:00:30"))
    assert next_wakeup(state, steps, at("07:00:30")) == at("07:10:00")
    assert next_wakeup(state, steps, at("07:10:00")) == at("08:30:00")
    assert next_wakeup(state, steps, at("08:30:00")) is None


def test_next_wakeup_includes_alarm_time_for_skip():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    assert next_wakeup(state, [], at("06:00:00")) == at("06:59:55")
    assert next_wakeup(state, [HEATER], at("06:31:00")) == at("06:59:55")


def test_next_wakeup_ignores_disabled_steps():
    state = home_state()
    off = Step("script.heater", -30, enabled=False)
    assert next_wakeup(state, [off], at("06:00:00")) == at("06:59:55")


def test_next_wakeup_ignores_steps_of_alarms_that_cant_run_them():
    state = RoutineState(last_location="home")
    enter(state, "09:30:00", "06:00:00")
    enter(state, "07:00:00", "06:01:00")
    step = Step("script.heater", -30)
    # the 09:30 alarm sleeps behind the 07:00 alarm, so its 09:00 step isn't wanted
    assert next_wakeup(state, [step], at("08:30:01")) == at("11:00:00")


def test_next_wakeup_ignores_steps_of_skipped_alarm():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    settle(state, at("07:00:00"))
    assert state.current.skipped
    step = Step("script.after", 10)
    assert next_wakeup(state, [step], at("07:00:00")) == at("08:30:00")


def test_next_wakeup_with_nothing_tracked_is_none():
    assert next_wakeup(RoutineState(), [HEATER], at("06:00:00")) is None


def test_restart_doesnt_start_step_lost_while_away():
    state = home_state()
    step = Step("script.after", 10)
    state.last_location = "not_home"
    assert run(state, [step], "07:10:00") == []
    state.last_location = "home"
    assert run(state, [step], "07:12:00") == []
    assert restart(state, [step], "07:13:00") == []


def test_restart_doesnt_start_step_of_alarm_seen_late_while_running():
    state = RoutineState(last_location="home")
    enter(state, "07:00:00", "07:02:00")
    assert state.current.seen_late
    step = Step("script.at", 0)
    assert run(state, [step], "07:02:00") == []
    assert restart(state, [step], "07:03:00") == []


def test_restart_doesnt_start_step_lost_while_routine_was_off():
    state = home_state()
    step = Step("script.at", 0)
    assert run(state, [step], "07:00:00", routine_on=False) == []
    assert run(state, [step], "07:01:00", routine_on=True) == []
    assert restart(state, [step], "07:02:00", routine_on=True) == []


def test_alarm_first_seen_at_restart_keeps_the_5_minute_rule():
    state = RoutineState(last_location="home")
    enter(state, "07:00:00", "07:03:00")
    assert state.current.seen_late
    step = Step("script.at", 0)
    assert restart(state, [step], "07:03:00") == ["script.at"]


def test_restart_doesnt_start_later_step_of_alarm_seen_late_while_running():
    state = RoutineState(last_location="home")
    enter(state, "07:00:00", "07:02:00")
    step = Step("script.after", 10)
    assert run(state, [step], "07:02:00") == []
    assert restart(state, [step], "07:11:00") == []


def test_seen_late_alarm_drops_future_steps_at_once():
    state = RoutineState(last_location="home")
    enter(state, "07:00:00", "07:02:00")
    step = Step("script.after", 10)
    assert run(state, [step], "07:02:00") == []
    assert state.current.dropped == {"script.after"}


def test_connection_drop_returning_same_alarm_catches_up():
    state = home_state()
    observe_no_alarm(state, at("06:26:00"))
    assert state.current is None
    enter(state, "07:00:00", "06:45:00")
    assert run(state, [HEATER], "06:45:00") == ["script.heater"]


def test_restart_drops_step_when_routine_is_off():
    state = home_state()
    assert restart(state, [HEATER], "06:31:00", routine_on=False) == []
    assert state.current.dropped == {"script.heater"}


def test_restart_drops_step_when_skip_is_on():
    state = home_state()
    set_skip(state, True, at("06:00:00"))
    assert restart(state, [HEATER], "06:31:00") == []
    assert state.current.dropped == {"script.heater"}
    assert state.skip_next


def test_two_steps_for_one_item_each_run_once_under_their_own_key():
    state = home_state()
    on = Step("light.lamp", -30, id="a", action="turn_on")
    off = Step("light.lamp", -20, id="b", action="turn_off")

    first = steps_to_run(state, [on, off], True, at("06:30:00"))
    assert [step.id for _, step in first] == ["a"]
    first[0][0].ran.add(first[0][1].key)
    second = steps_to_run(state, [on, off], True, at("06:40:00"))

    assert [step.id for _, step in second] == ["b"]


def test_a_step_without_an_id_is_tracked_by_its_item():
    assert HEATER.key == "script.heater"
    assert Step("light.lamp", 0, id="a").key == "a"


def test_a_late_step_is_dropped_under_its_key():
    state = home_state()
    lamp = Step("light.lamp", -30, id="a", action="turn_on")

    assert run(state, [lamp], "07:00:30") == []
    assert state.alarms[0].dropped == {"a"}


def test_restart_drops_a_late_step_under_its_key():
    state = home_state()
    lamp = Step("light.lamp", -30, id="a", action="turn_on")

    assert restart(state, [lamp], "06:40:00") == []
    assert state.alarms[0].dropped == {"a"}
