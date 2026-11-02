from datetime import datetime, timezone

from rules import (
    CLOCK_SKEW,
    Alarm,
    IgnoreReason,
    RoutineState,
    change_clock,
    observe_entry,
    observe_no_alarm,
    recheck_current,
    settle,
)

CLOCK = "com.sec.android.app.clockpackage"
ROUTINES = "com.samsung.android.app.routines"
NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)


def at(hms: str) -> datetime:
    hour, minute, second = (int(part) for part in hms.split(":"))
    return NOW.replace(hour=hour, minute=minute, second=second)


def enter(state: RoutineState, entry: str, now: str, package: str = CLOCK) -> None:
    observe_entry(state, at(entry), package, CLOCK, True, at(now))


def state_with_alarm(entry: str = "09:00:00", now: str = "08:00:00") -> RoutineState:
    state = RoutineState()
    enter(state, entry, now)
    return state


def test_same_time_is_a_repeat():
    state = state_with_alarm()
    alarm = state.current
    alarm.ran.add("step")
    enter(state, "09:00:00", "08:01:00")
    assert state.current is alarm
    assert state.alarms == [alarm]
    assert alarm.ran == {"step"}


def test_within_20_minutes_is_same_alarm():
    state = state_with_alarm()
    alarm = state.current
    alarm.ran.add("step")
    enter(state, "09:15:00", "08:01:00")
    assert state.current is alarm
    assert state.alarms == [alarm]
    assert alarm.ran == {"step"}
    assert alarm.time == at("09:15:00")
    assert alarm.latest == at("09:15:00")


def test_exactly_20_minutes_is_same_alarm():
    state = state_with_alarm()
    alarm = state.current
    enter(state, "09:20:00", "08:01:00")
    assert state.current is alarm
    assert len(state.alarms) == 1
    assert alarm.time == at("09:20:00")


def test_more_than_20_minutes_is_a_new_alarm():
    state = state_with_alarm()
    first = state.current
    enter(state, "09:21:00", "08:01:00")
    assert state.current is not first
    assert state.current.time == at("09:21:00")
    assert state.alarms == [first, state.current]
    assert first.time == at("09:00:00")


def test_earlier_is_a_new_alarm():
    state = state_with_alarm()
    first = state.current
    enter(state, "08:30:00", "08:01:00")
    assert state.current is not first
    assert state.current.time == at("08:30:00")
    assert first in state.alarms
    assert first.time == at("09:00:00")
    assert not first.cancelled


def test_earlier_entry_that_doesnt_count_keeps_current():
    state = state_with_alarm()
    alarm = state.current
    enter(state, "08:30:00", "08:01:00", package=ROUTINES)
    assert state.current is alarm
    assert not alarm.cancelled


def test_later_entry_that_doesnt_count_cancels():
    state = state_with_alarm()
    alarm = state.current
    alarm.ran.add("step")
    enter(state, "09:30:00", "08:01:00", package=ROUTINES)
    assert alarm.cancelled
    assert state.current is None
    assert alarm.ran == {"step"}
    assert alarm in state.alarms


def test_no_alarm_cancels_before_alarm_time():
    state = state_with_alarm()
    alarm = state.current
    observe_no_alarm(state, at("08:30:00"))
    assert alarm.cancelled
    assert state.current is None


def test_no_alarm_after_alarm_time_doesnt_cancel():
    state = state_with_alarm()
    alarm = state.current
    observe_no_alarm(state, at("09:00:30"))
    assert alarm.went_off
    assert not alarm.cancelled
    assert state.current is alarm


def test_no_alarm_with_nothing_tracked_does_nothing():
    state = RoutineState()
    observe_no_alarm(state, at("08:00:00"))
    assert state.current is None
    assert state.alarms == []


def test_change_at_alarm_time_means_it_rang():
    state = state_with_alarm()
    alarm = state.current
    enter(state, "09:30:00", "09:00:00", package=ROUTINES)
    assert alarm.went_off
    assert not alarm.cancelled
    assert state.current is alarm


def test_change_within_5_seconds_before_means_it_rang():
    state = state_with_alarm()
    alarm = state.current
    enter(state, "09:30:00", "08:59:56", package=ROUTINES)
    assert alarm.went_off
    assert not alarm.cancelled


def test_change_6_seconds_before_is_cancelled():
    state = state_with_alarm()
    alarm = state.current
    enter(state, "09:30:00", "08:59:54", package=ROUTINES)
    assert not alarm.went_off
    assert alarm.cancelled
    assert state.current is None


def test_snooze_after_ring_is_same_alarm_and_keeps_its_time():
    state = state_with_alarm("09:03:00")
    alarm = state.current
    enter(state, "09:08:00", "09:03:01")
    assert state.current is alarm
    assert len(state.alarms) == 1
    assert alarm.went_off
    assert alarm.time == at("09:03:00")
    assert alarm.latest == at("09:08:00")


def test_snoozes_chain_past_20_minutes():
    state = state_with_alarm("09:03:00")
    alarm = state.current
    arrivals = [
        ("09:08:00", "09:03:01"),
        ("09:13:00", "09:08:01"),
        ("09:18:00", "09:13:01"),
        ("09:23:00", "09:18:01"),
        ("09:28:00", "09:23:01"),
    ]
    for entry, now in arrivals:
        enter(state, entry, now)
    assert state.alarms == [alarm]
    assert state.current is alarm
    assert alarm.time == at("09:03:00")
    assert alarm.latest == at("09:28:00")


def test_same_time_comes_back_after_cancel():
    state = state_with_alarm()
    alarm = state.current
    alarm.ran.add("step")
    enter(state, "09:30:00", "08:01:00", package=ROUTINES)
    assert state.current is None
    enter(state, "09:00:00", "08:02:00")
    assert state.current is alarm
    assert not alarm.cancelled
    assert alarm.ran == {"step"}
    assert state.alarms == [alarm]


def test_new_alarm_keeps_gone_off_alarm_in_list():
    state = state_with_alarm("09:00:00")
    first = state.current
    first.ran.add("step")
    enter(state, "10:00:00", "09:00:01")
    assert first.went_off
    assert state.current is not first
    assert state.alarms == [first, state.current]
    assert first.ran == {"step"}


def test_alarm_behind_earlier_alarm_comes_back_with_its_record():
    state = state_with_alarm("09:00:00")
    nine = state.current
    nine.ran.add("step")
    enter(state, "07:00:00", "06:00:00")
    seven = state.current
    assert seven is not nine
    assert nine in state.alarms
    enter(state, "09:00:00", "07:00:01")
    assert state.current is nine
    assert nine.ran == {"step"}
    assert state.alarms == [nine, seven]


def test_record_removed_90_minutes_after_alarm():
    state = state_with_alarm("09:00:00")
    alarm = state.current
    observe_no_alarm(state, at("10:30:00"))
    assert state.alarms == [alarm]
    observe_no_alarm(state, at("10:30:01"))
    assert state.alarms == []
    assert state.current is None


def test_settle_removes_other_old_alarms_and_keeps_current():
    state = state_with_alarm("09:00:00")
    old = state.current
    enter(state, "13:00:00", "09:00:01")
    current = state.current
    settle(state, at("10:45:00"))
    assert state.alarms == [current]
    assert old not in state.alarms
    assert state.current is current


def test_stale_entry_doesnt_become_current():
    state = RoutineState()
    enter(state, "06:00:00", "08:00:00")
    assert state.current is None
    assert state.alarms == []
    assert state.last_ignored.reason is IgnoreReason.IN_THE_PAST
    assert state.last_ignored.time == at("06:00:00")


def test_stale_entry_doesnt_cancel_current():
    state = state_with_alarm()
    alarm = state.current
    enter(state, "06:00:00", "08:00:00", package=ROUTINES)
    assert state.current is alarm
    assert not alarm.cancelled


def test_ignored_entry_is_recorded_with_reason():
    state = state_with_alarm()
    enter(state, "07:30:00", "07:00:00", package=ROUTINES)
    ignored = state.last_ignored
    assert ignored.time == at("07:30:00")
    assert ignored.package == ROUTINES
    assert ignored.reason is IgnoreReason.WRONG_APP
    enter(state, "07:45:03", "07:00:01")
    assert state.last_ignored.reason is IgnoreReason.NOT_ON_THE_MINUTE


def test_change_clock_clears_current_and_keeps_records():
    state = state_with_alarm()
    alarm = state.current
    alarm.ran.add("step")
    change_clock(state)
    assert state.current is None
    assert state.alarms == [alarm]
    assert alarm.ran == {"step"}


def test_skip_next_is_used_up_when_the_alarm_goes_off():
    state = state_with_alarm()
    alarm = state.current
    state.skip_next = True
    settle(state, at("08:59:00"))
    assert not alarm.skipped
    assert state.skip_next
    settle(state, at("09:00:00") - CLOCK_SKEW)
    assert alarm.went_off
    assert alarm.skipped
    assert not state.skip_next


def test_skip_next_turned_on_after_ring_waits_for_next_alarm():
    state = state_with_alarm()
    alarm = state.current
    settle(state, at("09:00:01"))
    state.skip_next = True
    settle(state, at("09:00:02"))
    assert not alarm.skipped
    assert state.skip_next


def test_new_alarm_already_past_is_marked_gone_off():
    state = RoutineState()
    enter(state, "09:00:00", "09:10:00")
    assert state.current.went_off


def test_alarm_defaults_are_not_shared():
    first = Alarm(time=at("09:00:00"), latest=at("09:00:00"))
    second = Alarm(time=at("10:00:00"), latest=at("10:00:00"))
    first.ran.add("step")
    first.dropped.add("other")
    assert second.ran == set()
    assert second.dropped == set()
    assert RoutineState().alarms == []


def test_alarm_first_seen_after_it_passed_leaves_skip_on():
    state = RoutineState(skip_next=True)
    enter(state, "09:00:00", "09:06:00")
    alarm = state.current
    assert alarm.went_off
    assert alarm.seen_late
    assert not alarm.skipped
    assert state.skip_next


def test_alarm_returning_after_it_passed_leaves_skip_on():
    state = state_with_alarm()
    alarm = state.current
    enter(state, "09:30:00", "08:01:00", package=ROUTINES)
    assert alarm.cancelled
    state.skip_next = True
    enter(state, "09:00:00", "09:06:00")
    assert state.current is alarm
    assert not alarm.cancelled
    assert alarm.went_off
    assert alarm.seen_late
    assert not alarm.skipped
    assert state.skip_next


def test_alarm_seen_as_it_rings_uses_up_the_skip():
    state = RoutineState(skip_next=True)
    enter(state, "09:00:00", "09:00:03")
    alarm = state.current
    assert alarm.went_off
    assert not alarm.seen_late
    assert alarm.skipped
    assert not state.skip_next


def alarm_followed_with_seconds(now: str = "08:00:00") -> RoutineState:
    """The seconds check is off and an alarm at 09:00:03 is followed."""
    state = RoutineState()
    observe_entry(state, at("09:00:03"), CLOCK, CLOCK, False, at(now))
    assert state.current is not None
    return state


def test_turning_the_seconds_check_on_cancels_an_entry_it_now_rejects():
    state = alarm_followed_with_seconds()
    alarm = state.current

    recheck_current(state, at("09:00:03"), CLOCK, CLOCK, True, at("08:01:00"))

    assert state.current is None
    assert alarm.cancelled
    assert state.alarms == [alarm]


def test_recheck_leaves_an_entry_that_still_counts():
    state = alarm_followed_with_seconds()
    alarm = state.current

    recheck_current(state, at("09:00:03"), CLOCK, CLOCK, False, at("08:01:00"))

    assert state.current is alarm
    assert not alarm.cancelled


def test_recheck_leaves_the_alarm_when_the_entry_is_a_different_time():
    # The sensor shows an earlier entry. The followed alarm is hidden behind it and must survive.
    state = alarm_followed_with_seconds()
    alarm = state.current

    recheck_current(state, at("08:30:03"), CLOCK, CLOCK, True, at("08:01:00"))

    assert state.current is alarm
    assert not alarm.cancelled


def test_recheck_leaves_an_alarm_that_already_went_off():
    state = alarm_followed_with_seconds()
    alarm = state.current

    recheck_current(state, at("09:00:03"), CLOCK, CLOCK, True, at("09:00:30"))

    assert state.current is alarm
    assert alarm.went_off


def test_turning_the_seconds_check_off_again_restores_the_alarm_and_its_record():
    state = alarm_followed_with_seconds()
    alarm = state.current
    alarm.ran.add("step")
    recheck_current(state, at("09:00:03"), CLOCK, CLOCK, True, at("08:01:00"))
    assert state.current is None

    recheck_current(state, at("09:00:03"), CLOCK, CLOCK, False, at("08:02:00"))
    observe_entry(state, at("09:00:03"), CLOCK, CLOCK, False, at("08:02:00"))

    assert state.current is alarm
    assert not alarm.cancelled
    assert alarm.ran == {"step"}
    assert state.alarms == [alarm]
