import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from custom_components.morning_routine.devices import describe_device, device_calls, step_detail
from custom_components.morning_routine.rules import Step

LAMP = "light.lamp"
HEATER = "climate.heater"
HALL = "climate.hall"
RANGE = 1 + 2 + 128 + 256
ONE_TEMPERATURE = 1 + 128 + 256


def set_hall(hass, mode: str, low=None, high=None, temperature=None) -> None:
    hass.states.async_set(
        HALL,
        mode,
        {
            "supported_features": RANGE,
            "min_temp": 45,
            "max_temp": 95,
            "target_temp_low": low,
            "target_temp_high": high,
            "temperature": temperature,
        },
    )


BRIGHTNESS = {"number": {"min": 1, "max": 100, "step": 1, "mode": "slider", "unit_of_measurement": "%"}}
TURN_OFF = {"action": "turn_off", "name": "Turn off", "settings": []}


@pytest.fixture
def fahrenheit(hass) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM


def degrees(low, high, step, unit="°F") -> dict:
    return {"number": {"min": low, "max": high, "step": step, "mode": "slider", "unit_of_measurement": unit}}


def setting(actions: list, action: str, key: str) -> dict:
    chosen = next(entry for entry in actions if entry["action"] == action)
    return next(entry for entry in chosen["settings"] if entry["key"] == key)


async def test_a_light_that_dims_describes_turn_on_with_an_optional_brightness(hass):
    hass.states.async_set(LAMP, "off", {"supported_color_modes": ["brightness"]})

    assert describe_device(hass, LAMP) == [
        {
            "action": "turn_on",
            "name": "Turn on",
            "settings": [
                {
                    "key": "brightness",
                    "name": "Brightness",
                    "optional": True,
                    "hint": "as it was",
                    "start": 100,
                    "selector": BRIGHTNESS,
                }
            ],
        },
        TURN_OFF,
    ]


@pytest.mark.parametrize(("reported", "start"), [(102, 40), (1, 1), (255, 100), (None, 100)])
async def test_brightness_starts_at_the_lights_current_brightness(hass, reported, start):
    hass.states.async_set(LAMP, "on", {"supported_color_modes": ["brightness"], "brightness": reported})

    assert setting(describe_device(hass, LAMP), "turn_on", "brightness")["start"] == start


@pytest.mark.parametrize("modes", [["onoff"], None])
async def test_a_light_that_only_switches_has_no_settings(hass, modes):
    hass.states.async_set(LAMP, "off", {"supported_color_modes": modes})

    assert describe_device(hass, LAMP) == [{"action": "turn_on", "name": "Turn on", "settings": []}, TURN_OFF]


async def test_a_light_dims_when_it_reports_any_mode_other_than_on_off(hass):
    hass.states.async_set(LAMP, "off", {"supported_color_modes": ["color_temp", "xy"]})

    assert [entry["key"] for entry in describe_device(hass, LAMP)[0]["settings"]] == ["brightness"]


async def test_a_one_temperature_thermostat_describes_its_limits_step_and_start(hass, fahrenheit):
    hass.states.async_set(HEATER, "off", {"supported_features": ONE_TEMPERATURE, "min_temp": 86, "max_temp": 125})

    assert describe_device(hass, HEATER) == [
        {
            "action": "turn_on",
            "name": "Turn on",
            "settings": [
                {
                    "key": "temperature",
                    "name": "Temperature",
                    "optional": True,
                    "hint": "last setting",
                    # The middle of 86 to 125 is 105.5, which rounds to a whole step.
                    "start": 106,
                    "selector": degrees(86, 125, 1),
                }
            ],
        },
        TURN_OFF,
    ]


@pytest.mark.parametrize(("reported", "start"), [(110, 110), (200, 106), ("warm", 106)])
async def test_a_temperature_starts_at_the_thermostats_setting_when_that_is_within_its_limits(
    hass, fahrenheit, reported, start
):
    hass.states.async_set(
        HEATER, "heat", {"supported_features": ONE_TEMPERATURE, "min_temp": 86, "max_temp": 125, "temperature": reported}
    )

    assert setting(describe_device(hass, HEATER), "turn_on", "temperature")["start"] == start


async def test_a_thermostat_that_reports_its_own_step_uses_it(hass, fahrenheit):
    hass.states.async_set(
        HEATER, "off", {"supported_features": ONE_TEMPERATURE, "min_temp": 86, "max_temp": 125, "target_temp_step": 0.5}
    )

    temperature = setting(describe_device(hass, HEATER), "turn_on", "temperature")

    assert (temperature["selector"], temperature["start"]) == (degrees(86, 125, 0.5), 105.5)


async def test_a_thermostat_offers_only_the_actions_it_supports(hass):
    hass.states.async_set(HEATER, "heat", {"supported_features": 256})

    assert describe_device(hass, HEATER) == [{"action": "turn_on", "name": "Turn on", "settings": []}]


async def test_a_thermostat_that_can_do_neither_is_not_offered(hass):
    hass.states.async_set(HEATER, "heat", {"supported_features": 1})

    assert describe_device(hass, HEATER) is None


async def test_a_range_thermostat_describes_two_required_settings(hass, fahrenheit):
    set_hall(hass, "heat_cool", low=65, high=72)

    assert describe_device(hass, HALL) == [
        {
            "action": "set_temperature",
            "name": "Set temperatures",
            "settings": [
                {"key": "heat_to", "name": "Heat to", "optional": False, "start": 65, "selector": degrees(45, 95, 1)},
                {"key": "cool_to", "name": "Cool to", "optional": False, "start": 72, "selector": degrees(45, 95, 1)},
            ],
        }
    ]


@pytest.mark.parametrize(("low", "high"), [(None, None), (72, 65), (70, 70), (40, 72), (65, 99)])
async def test_a_range_thermostat_without_two_usable_numbers_starts_a_third_and_two_thirds_up(
    hass, fahrenheit, low, high
):
    set_hall(hass, "heat", low=low, high=high)

    actions = describe_device(hass, HALL)

    assert setting(actions, "set_temperature", "heat_to")["start"] == 62
    assert setting(actions, "set_temperature", "cool_to")["start"] == 78


async def test_a_thermostat_with_no_limits_gets_home_assistants_defaults(hass, fahrenheit):
    hass.states.async_set(HEATER, "off", {"supported_features": ONE_TEMPERATURE})

    assert setting(describe_device(hass, HEATER), "turn_on", "temperature")["selector"] == degrees(45, 95, 1)

    hass.config.units = METRIC_SYSTEM

    assert setting(describe_device(hass, HEATER), "turn_on", "temperature")["selector"] == degrees(7, 35, 0.5, "°C")


async def test_celsius_uses_half_degree_steps(hass):
    set_hall(hass, "heat")

    actions = describe_device(hass, HALL)

    assert setting(actions, "set_temperature", "heat_to")["selector"] == degrees(45, 95, 0.5, "°C")
    assert setting(actions, "set_temperature", "heat_to")["start"] == 61.5
    assert setting(actions, "set_temperature", "cool_to")["start"] == 78.5


@pytest.mark.parametrize("entity_id", ["switch.pump", "lock.front_door", "cover.garage", "script.anything"])
async def test_other_device_types_are_not_offered(hass, entity_id):
    hass.states.async_set(entity_id, "off")

    assert describe_device(hass, entity_id) is None


async def test_a_device_that_is_unavailable_or_missing_is_not_offered(hass):
    hass.states.async_set(LAMP, "unavailable")

    assert describe_device(hass, LAMP) is None
    assert describe_device(hass, "light.never_existed") is None


@pytest.mark.parametrize(
    ("step", "words"),
    [
        (Step(LAMP, 0, id="a", action="turn_on"), "Turn on"),
        (Step(LAMP, 0, id="a", action="turn_on", brightness=40), "Turn on at 40%"),
        (Step(HEATER, 0, id="a", action="turn_on", temperature=115), "Turn on at 115°F"),
        (Step(HEATER, 0, id="a", action="turn_on", temperature=74.5), "Turn on at 74.5°F"),
        (Step(HEATER, 0, id="a", action="turn_off"), "Turn off"),
        (Step(HALL, 0, id="a", action="set_temperature", heat_to=68, cool_to=74), "Heat to 68°F, cool to 74°F"),
        (Step("script.wake", 0), ""),
    ],
)
async def test_step_detail_says_what_a_step_does(hass, fahrenheit, step, words):
    assert step_detail(hass, step) == words


async def test_light_calls(hass):
    on = Step(LAMP, 0, id="a", action="turn_on")
    dim = Step(LAMP, 0, id="b", action="turn_on", brightness=40)
    off = Step(LAMP, 0, id="c", action="turn_off")

    assert device_calls(hass, on) == [("light", "turn_on", {"entity_id": LAMP})]
    assert device_calls(hass, dim) == [("light", "turn_on", {"entity_id": LAMP, "brightness_pct": 40})]
    assert device_calls(hass, off) == [("light", "turn_off", {"entity_id": LAMP})]


async def test_thermostat_turn_on_sets_the_temperature_after_turning_on(hass):
    plain = Step(HEATER, 0, id="a", action="turn_on")
    warm = Step(HEATER, 0, id="b", action="turn_on", temperature=115)
    off = Step(HEATER, 0, id="c", action="turn_off")

    assert device_calls(hass, plain) == [("climate", "turn_on", {"entity_id": HEATER})]
    assert device_calls(hass, warm) == [
        ("climate", "turn_on", {"entity_id": HEATER}),
        ("climate", "set_temperature", {"entity_id": HEATER, "temperature": 115}),
    ]
    assert device_calls(hass, off) == [("climate", "turn_off", {"entity_id": HEATER})]


async def test_range_step_sends_both_numbers_in_heat_and_cool_mode(hass):
    set_hall(hass, "heat_cool", low=65, high=72)
    step = Step(HALL, 0, id="a", action="set_temperature", heat_to=68, cool_to=74)

    assert device_calls(hass, step) == [
        ("climate", "set_temperature", {"entity_id": HALL, "target_temp_low": 68, "target_temp_high": 74})
    ]


@pytest.mark.parametrize(("mode", "sent"), [("heat", 68), ("cool", 74), ("auto", 68)])
async def test_range_step_sends_the_one_number_that_fits_the_mode(hass, mode, sent):
    set_hall(hass, mode, temperature=70)
    step = Step(HALL, 0, id="a", action="set_temperature", heat_to=68, cool_to=74)

    assert device_calls(hass, step) == [("climate", "set_temperature", {"entity_id": HALL, "temperature": sent})]


async def test_range_step_sends_both_numbers_when_the_thermostat_shows_both(hass):
    set_hall(hass, "auto", low=65, high=72)
    step = Step(HALL, 0, id="a", action="set_temperature", heat_to=68, cool_to=74)

    assert device_calls(hass, step)[0][2] == {"entity_id": HALL, "target_temp_low": 68, "target_temp_high": 74}


@pytest.mark.parametrize("mode", ["off", "unavailable", "unknown", "fan_only", "dry"])
async def test_range_step_fails_when_the_thermostat_takes_no_temperature(hass, mode):
    set_hall(hass, mode)
    step = Step(HALL, 0, id="a", action="set_temperature", heat_to=68, cool_to=74)

    with pytest.raises(HomeAssistantError):
        device_calls(hass, step)


async def test_range_step_fails_when_the_thermostat_is_gone(hass):
    step = Step(HALL, 0, id="a", action="set_temperature", heat_to=68, cool_to=74)

    with pytest.raises(HomeAssistantError):
        device_calls(hass, step)


@pytest.mark.parametrize(("mode", "sent"), [("heat", 68), ("cool", 74)])
async def test_range_step_in_heat_or_cool_mode_sends_one_number_even_when_both_are_shown(hass, mode, sent):
    set_hall(hass, mode, low=65, high=72)
    step = Step(HALL, 0, id="a", action="set_temperature", heat_to=68, cool_to=74)

    assert device_calls(hass, step) == [("climate", "set_temperature", {"entity_id": HALL, "temperature": sent})]
