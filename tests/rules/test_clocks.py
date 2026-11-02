from clocks import GOOGLE_CLOCK, NOT_CLOCKS, SAMSUNG_CLOCK, clock_options

ROUTINES = "com.samsung.android.app.routines"


def test_google_clock_on_every_phone():
    assert GOOGLE_CLOCK in clock_options("Pixel", set(), None)


def test_samsung_clock_on_a_samsung_phone():
    assert SAMSUNG_CLOCK in clock_options("samsung", set(), None)


def test_samsung_check_ignores_case():
    assert SAMSUNG_CLOCK in clock_options("Samsung", set(), None)


def test_samsung_clock_hidden_on_other_phones():
    assert SAMSUNG_CLOCK not in clock_options("Pixel", set(), None)


def test_samsung_clock_hidden_when_manufacturer_unknown():
    assert SAMSUNG_CLOCK not in clock_options(None, set(), None)


def test_samsung_clock_shown_if_reported():
    assert SAMSUNG_CLOCK in clock_options("Pixel", {SAMSUNG_CLOCK}, None)


def test_routines_app_is_never_offered():
    assert ROUTINES in NOT_CLOCKS
    assert ROUTINES not in clock_options("samsung", {ROUTINES}, None)


def test_unknown_app_shows_its_package():
    assert clock_options(None, {"com.example.clock"}, None)["com.example.clock"] == "com.example.clock"


def test_known_apps_get_plain_names():
    options = clock_options("samsung", set(), None)
    assert options[GOOGLE_CLOCK] != GOOGLE_CLOCK
    assert options[SAMSUNG_CLOCK] != SAMSUNG_CLOCK


def test_chosen_clock_always_offered():
    assert "com.example.chosen" in clock_options("Pixel", set(), "com.example.chosen")
