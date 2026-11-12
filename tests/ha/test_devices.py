import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.morning_routine.devices import device_calls, device_info
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


@pytest.mark.parametrize(
    ("modes", "dims"),
    [(["onoff"], False), (["brightness"], True), (["color_temp", "xy"], True), (None, False)],
)
async def test_a_light_can_turn_on_and_off_and_dims_when_it_reports_more_than_on_off(hass, modes, dims):
    hass.states.async_set(LAMP, "off", {"supported_color_modes": modes})

    assert device_info(hass, LAMP) == {"type": "light", "actions": ["turn_on", "turn_off"], "brightness": dims}


async def test_a_thermostat_with_one_temperature(hass):
    hass.states.async_set(HEATER, "off", {"supported_features": ONE_TEMPERATURE, "min_temp": 86, "max_temp": 125})

    assert device_info(hass, HEATER) == {
        "type": "thermostat",
        "actions": ["turn_on", "turn_off"],
        "temperature": True,
        "min_temp": 86,
        "max_temp": 125,
    }


async def test_a_thermostat_offers_only_the_actions_it_supports(hass):
    hass.states.async_set(HEATER, "heat", {"supported_features": 256})

    info = device_info(hass, HEATER)

    assert info["actions"] == ["turn_on"]
    assert info["temperature"] is False


async def test_a_thermostat_that_can_do_neither_is_not_offered(hass):
    hass.states.async_set(HEATER, "heat", {"supported_features": 1})

    assert device_info(hass, HEATER) is None


async def test_a_thermostat_that_takes_a_range(hass):
    set_hall(hass, "heat_cool", low=65, high=72)

    assert device_info(hass, HALL) == {
        "type": "thermostat_range",
        "actions": ["set_temperature"],
        "min_temp": 45,
        "max_temp": 95,
    }


@pytest.mark.parametrize("entity_id", ["switch.pump", "lock.front_door", "cover.garage", "script.anything"])
async def test_other_device_types_are_not_offered(hass, entity_id):
    hass.states.async_set(entity_id, "off")

    assert device_info(hass, entity_id) is None


async def test_a_device_that_is_unavailable_or_missing_is_not_offered(hass):
    hass.states.async_set(LAMP, "unavailable")

    assert device_info(hass, LAMP) is None
    assert device_info(hass, "light.never_existed") is None


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
