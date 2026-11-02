from datetime import datetime, timedelta, timezone

from rules import IgnoreReason, check_entry

CLOCK = "com.sec.android.app.clockpackage"
ROUTINES = "com.samsung.android.app.routines"
NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)


def at(hms: str) -> datetime:
    hour, minute, second = (int(part) for part in hms.split(":"))
    return NOW.replace(hour=hour, minute=minute, second=second)


def test_real_alarm_counts():
    assert check_entry(at("09:03:00"), CLOCK, CLOCK, True, NOW) is None


def test_no_clock_chosen():
    assert check_entry(at("09:03:00"), CLOCK, None, True, NOW) is IgnoreReason.NO_CLOCK


def test_other_app():
    assert check_entry(at("07:30:00"), ROUTINES, CLOCK, True, NOW) is IgnoreReason.WRONG_APP


def test_seconds_not_zero():
    assert check_entry(at("07:00:03"), CLOCK, CLOCK, True, NOW) is IgnoreReason.NOT_ON_THE_MINUTE


def test_seconds_check_can_be_off():
    assert check_entry(at("07:00:03"), CLOCK, CLOCK, False, NOW) is None


def test_stale_value_is_ignored():
    assert check_entry(NOW - timedelta(minutes=91), CLOCK, CLOCK, True, NOW) is IgnoreReason.IN_THE_PAST


def test_value_just_inside_the_kept_window_counts():
    assert check_entry(NOW - timedelta(minutes=90), CLOCK, CLOCK, True, NOW) is None


def test_wrong_app_is_reported_before_seconds():
    assert check_entry(at("07:00:03"), ROUTINES, CLOCK, True, NOW) is IgnoreReason.WRONG_APP


def test_no_clock_is_reported_before_wrong_app():
    assert check_entry(at("07:00:03"), ROUTINES, None, True, NOW) is IgnoreReason.NO_CLOCK


def test_seconds_are_reported_before_stale():
    stale_with_seconds = NOW - timedelta(minutes=120) + timedelta(seconds=3)
    assert check_entry(stale_with_seconds, CLOCK, CLOCK, True, NOW) is IgnoreReason.NOT_ON_THE_MINUTE
