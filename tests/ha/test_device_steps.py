"""Checking light and thermostat steps that come from a person."""

import pytest
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import CLIENT_ID

from custom_components.morning_routine.const import DOMAIN
from custom_components.morning_routine.devices import describe_device
from custom_components.morning_routine.rules import Step


async def set_steps(hass, entry_id: str, steps: list) -> None:
    await hass.services.async_call(DOMAIN, "set_steps", {"config_entry_id": entry_id, "steps": steps}, blocking=True)
    await hass.async_block_till_done()


async def refused(hass, entry_id: str, steps: list) -> str:
    with pytest.raises(ServiceValidationError) as error:
        await set_steps(hass, entry_id, steps)
    return error.value.translation_key


async def test_a_light_step_needs_no_label(hass, loaded, lamp):
    await set_steps(hass, loaded.entry_id, [{"item": lamp, "offset_minutes": -10, "action": "turn_on", "brightness": 40}])

    (step,) = loaded.runtime_data.steps
    assert (step.item, step.offset_minutes, step.action, step.brightness) == (lamp, -10, "turn_on", 40)
    assert len(step.id) == 12


async def test_device_steps_are_saved_with_their_settings(hass, hass_storage, loaded, heater, hall):
    await set_steps(
        hass,
        loaded.entry_id,
        [
            {"item": heater, "offset_minutes": -20, "action": "turn_on", "temperature": 115, "id": "steam"},
            {"item": hall, "offset_minutes": -5, "action": "set_temperature", "heat_to": 68, "cool_to": 74, "id": "hall"},
        ],
    )

    assert hass_storage[f"{DOMAIN}.{loaded.entry_id}"]["data"]["steps"] == [
        {"item": heater, "offset_minutes": -20, "enabled": True, "id": "steam", "action": "turn_on", "temperature": 115},
        {
            "item": hall,
            "offset_minutes": -5,
            "enabled": True,
            "id": "hall",
            "action": "set_temperature",
            "heat_to": 68,
            "cool_to": 74,
        },
    ]


async def test_one_light_can_be_two_steps(hass, loaded, lamp):
    await set_steps(
        hass,
        loaded.entry_id,
        [
            {"item": lamp, "offset_minutes": -10, "action": "turn_on"},
            {"item": lamp, "offset_minutes": 30, "action": "turn_off"},
        ],
    )

    first, second = loaded.runtime_data.steps
    assert (first.action, second.action) == ("turn_on", "turn_off")
    assert first.id != second.id


async def test_a_list_sent_again_without_ids_keeps_the_ids(hass, loaded, lamp):
    steps = [
        {"item": lamp, "offset_minutes": -10, "action": "turn_on"},
        {"item": lamp, "offset_minutes": -5, "action": "turn_on", "brightness": 80},
        {"item": lamp, "offset_minutes": 30, "action": "turn_off"},
    ]
    await set_steps(hass, loaded.entry_id, steps)
    before = [step.id for step in loaded.runtime_data.steps]

    await set_steps(hass, loaded.entry_id, steps)

    assert [step.id for step in loaded.runtime_data.steps] == before
    assert len(set(before)) == 3


async def test_an_id_from_the_card_is_kept_when_the_step_is_retimed(hass, loaded, lamp):
    await set_steps(hass, loaded.entry_id, [{"item": lamp, "offset_minutes": -10, "action": "turn_on"}])
    step_id = loaded.runtime_data.steps[0].id

    await set_steps(hass, loaded.entry_id, [{"item": lamp, "offset_minutes": -25, "action": "turn_on", "id": step_id}])

    assert loaded.runtime_data.steps == [Step(lamp, -25, True, id=step_id, action="turn_on")]


async def test_two_steps_with_the_same_id_are_refused(hass, loaded, lamp):
    steps = [
        {"item": lamp, "offset_minutes": -10, "action": "turn_on", "id": "same"},
        {"item": lamp, "offset_minutes": 10, "action": "turn_off", "id": "same"},
    ]

    assert await refused(hass, loaded.entry_id, steps) == "invalid_step"
    assert loaded.runtime_data.steps == []


@pytest.mark.parametrize("item", ["switch.pump", "lock.front_door", "cover.garage", "light.never_existed"])
async def test_other_device_types_and_missing_devices_are_refused(hass, loaded, item):
    hass.states.async_set("switch.pump", "off")
    hass.states.async_set("lock.front_door", "locked")
    hass.states.async_set("cover.garage", "closed")

    key = await refused(hass, loaded.entry_id, [{"item": item, "offset_minutes": 0, "action": "turn_on"}])

    assert key == "item_not_allowed"


@pytest.mark.parametrize(
    ("step", "key"),
    [
        ({"item": "light.lamp", "action": "set_temperature"}, "action_not_offered"),
        ({"item": "light.lamp", "action": "run"}, "action_not_offered"),
        ({"item": "light.lamp"}, "invalid_step"),
        ({"item": "light.lamp", "action": "turn_on", "brightness": 0}, "brightness_out_of_range"),
        ({"item": "light.lamp", "action": "turn_on", "brightness": 101}, "brightness_out_of_range"),
        ({"item": "light.lamp", "action": "turn_on", "brightness": 40.5}, "brightness_out_of_range"),
        ({"item": "light.lamp", "action": "turn_on", "brightness": "40"}, "invalid_step"),
        ({"item": "light.lamp", "action": "turn_on", "brightness": True}, "invalid_step"),
        ({"item": "light.lamp", "action": "turn_off", "brightness": 40}, "invalid_step"),
        ({"item": "light.lamp", "action": "turn_on", "temperature": 70}, "invalid_step"),
        ({"item": "light.plain", "action": "turn_on", "brightness": 40}, "invalid_step"),
        ({"item": "climate.heater", "action": "set_temperature", "heat_to": 90, "cool_to": 100}, "action_not_offered"),
        ({"item": "climate.heater", "action": "turn_on", "temperature": 85}, "temperature_out_of_range"),
        ({"item": "climate.heater", "action": "turn_on", "temperature": 126}, "temperature_out_of_range"),
        ({"item": "climate.heater", "action": "turn_off", "temperature": 100}, "invalid_step"),
        ({"item": "climate.hall", "action": "turn_on"}, "action_not_offered"),
        ({"item": "climate.hall", "action": "turn_off"}, "action_not_offered"),
        ({"item": "climate.hall", "action": "set_temperature", "heat_to": 68}, "invalid_step"),
        ({"item": "climate.hall", "action": "set_temperature", "heat_to": 74, "cool_to": 68}, "heat_not_below_cool"),
        ({"item": "climate.hall", "action": "set_temperature", "heat_to": 70, "cool_to": 70}, "heat_not_below_cool"),
        ({"item": "climate.hall", "action": "set_temperature", "heat_to": 40, "cool_to": 70}, "temperature_out_of_range"),
        ({"item": "climate.hall", "action": "set_temperature", "heat_to": 70, "cool_to": 96}, "temperature_out_of_range"),
        ({"item": "climate.hall", "action": "set_temperature", "heat_to": 70, "cool_to": 74, "temperature": 72}, "invalid_step"),
        ({"item": "light.lamp", "action": "turn_on", "id": 5}, "invalid_step"),
        ({"item": "light.lamp", "action": "turn_on", "id": "x" * 65}, "invalid_step"),
    ],
)
async def test_a_device_step_that_does_not_fit_the_device_is_refused_and_changes_nothing(
    hass, loaded, lamp, heater, hall, step, key
):
    hass.states.async_set("light.plain", "off", {"supported_color_modes": ["onoff"]})
    await set_steps(hass, loaded.entry_id, [{"item": lamp, "offset_minutes": -10, "action": "turn_on", "id": "kept"}])

    assert await refused(hass, loaded.entry_id, [{"offset_minutes": 0, **step}]) == key
    assert loaded.runtime_data.steps == [Step(lamp, -10, True, id="kept", action="turn_on")]


@pytest.mark.parametrize(
    "step",
    [
        {"item": "script.test_step", "offset_minutes": 0, "action": "turn_on"},
        {"item": "script.test_step", "offset_minutes": 0, "brightness": 40},
    ],
)
async def test_a_script_takes_no_action_and_no_settings(hass, loaded, labeled_script, step):
    assert await refused(hass, loaded.entry_id, [step]) == "invalid_step"


async def test_a_script_step_may_name_the_run_action_and_keeps_its_item_as_its_key(hass, loaded, labeled_script):
    await set_steps(
        hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": 0, "action": "run", "id": labeled_script}]
    )

    assert loaded.runtime_data.steps == [Step(labeled_script, 0, True)]


async def test_an_unchanged_step_is_kept_when_its_device_is_unavailable_or_gone(hass, loaded, lamp, heater):
    await set_steps(
        hass,
        loaded.entry_id,
        [
            {"item": lamp, "offset_minutes": -10, "action": "turn_on", "brightness": 40, "id": "lamp"},
            {"item": heater, "offset_minutes": -20, "action": "turn_on", "temperature": 115, "id": "heater"},
        ],
    )
    hass.states.async_set(lamp, "unavailable")
    hass.states.async_remove(heater)

    await set_steps(
        hass,
        loaded.entry_id,
        [
            {"item": lamp, "offset_minutes": -15, "action": "turn_on", "brightness": 40, "id": "lamp", "enabled": False},
            {"item": heater, "offset_minutes": -20, "action": "turn_on", "temperature": 115, "id": "heater"},
        ],
    )

    first, second = loaded.runtime_data.steps
    assert (first.offset_minutes, first.enabled, first.brightness) == (-15, False, 40)
    assert second.temperature == 115


async def test_a_changed_step_for_a_device_that_is_gone_is_refused(hass, loaded, lamp):
    await set_steps(hass, loaded.entry_id, [{"item": lamp, "offset_minutes": -10, "action": "turn_on", "id": "lamp"}])
    hass.states.async_remove(lamp)

    key = await refused(
        hass, loaded.entry_id, [{"item": lamp, "offset_minutes": -10, "action": "turn_off", "id": "lamp"}]
    )

    assert key == "item_not_allowed"


async def test_a_temperature_refusal_names_the_range(hass, loaded, heater):
    with pytest.raises(ServiceValidationError) as error:
        await set_steps(
            hass, loaded.entry_id, [{"item": heater, "offset_minutes": 0, "action": "turn_on", "temperature": 200}]
        )

    assert error.value.translation_placeholders == {"item": heater, "low": "86", "high": "125"}


async def test_non_admin_adds_a_light_step(hass, loaded, lamp, household_member, hass_ws_client):
    refresh_token = await hass.auth.async_create_refresh_token(household_member, CLIENT_ID)
    client = await hass_ws_client(hass, hass.auth.async_create_access_token(refresh_token))

    await client.send_json_auto_id(
        {
            "type": "morning_routine/set_steps",
            "entry_id": loaded.entry_id,
            "steps": [{"item": lamp, "offset_minutes": -10, "enabled": True, "action": "turn_on", "brightness": 40}],
        }
    )
    result = await client.receive_json()

    assert result["success"], result
    assert loaded.runtime_data.steps[0].brightness == 40


async def test_a_refusal_over_websocket_carries_a_plain_sentence(hass, loaded, lamp, hass_ws_client):
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "morning_routine/set_steps",
            "entry_id": loaded.entry_id,
            "steps": [{"item": lamp, "offset_minutes": 0, "action": "turn_on", "brightness": 150}],
        }
    )
    result = await client.receive_json()

    assert not result["success"]
    assert result["error"]["message"].startswith("Brightness must be a whole number from 1 to 100")


async def test_a_list_sent_in_another_order_without_ids_keeps_each_steps_own_id(hass, loaded, lamp):
    dim = {"item": lamp, "offset_minutes": -30, "action": "turn_on", "brightness": 10}
    bright = {"item": lamp, "offset_minutes": 0, "action": "turn_on", "brightness": 100}
    await set_steps(hass, loaded.entry_id, [dim, bright])
    ids = {step.brightness: step.id for step in loaded.runtime_data.steps}

    await set_steps(hass, loaded.entry_id, [bright, dim])

    assert {step.brightness: step.id for step in loaded.runtime_data.steps} == ids


async def test_one_of_two_like_steps_sent_alone_without_an_id_keeps_its_own_id(hass, loaded, lamp):
    dim = {"item": lamp, "offset_minutes": -30, "action": "turn_on", "brightness": 10}
    bright = {"item": lamp, "offset_minutes": 0, "action": "turn_on", "brightness": 100}
    await set_steps(hass, loaded.entry_id, [dim, bright])
    bright_id = loaded.runtime_data.steps[1].id

    await set_steps(hass, loaded.entry_id, [bright])

    assert [step.id for step in loaded.runtime_data.steps] == [bright_id]


@pytest.mark.parametrize("item", ["light.lamp", "light.plain", "climate.heater", "climate.hall"])
async def test_the_description_and_the_checks_agree(hass, loaded, lamp, heater, hall, item):
    """Whatever the form is told it may offer, the checks accept. Anything else, they refuse."""
    hass.states.async_set("light.plain", "off", {"supported_color_modes": ["onoff"]})
    out_of_range = ("brightness_out_of_range", "temperature_out_of_range")

    for action in describe_device(hass, item):
        base = {"item": item, "offset_minutes": 0, "action": action["action"]}
        limits = {setting["key"]: setting["selector"]["number"] for setting in action["settings"]}
        starts = {setting["key"]: setting["start"] for setting in action["settings"]}
        required = {setting["key"]: setting["start"] for setting in action["settings"] if not setting["optional"]}

        # A new step can be saved without moving a slider, and an optional setting can be left out.
        await set_steps(hass, loaded.entry_id, [{**base, **starts}])
        await set_steps(hass, loaded.entry_id, [{**base, **required}])

        if action["action"] == "set_temperature":
            ends = [{"heat_to": limits["heat_to"]["min"], "cool_to": limits["cool_to"]["max"]}]
        else:
            ends = [{key: limit[end]} for key, limit in limits.items() for end in ("min", "max")]
        for settings in ends:
            await set_steps(hass, loaded.entry_id, [{**base, **settings}])

        for key, limit in limits.items():
            for outside in (limit["min"] - 1, limit["max"] + 1):
                assert await refused(hass, loaded.entry_id, [{**base, **starts, key: outside}]) in out_of_range

        for key in ("brightness", "temperature", "heat_to", "cool_to"):
            if key not in limits:
                assert await refused(hass, loaded.entry_id, [{**base, **starts, key: 50}]) == "invalid_step"


async def test_a_value_between_slider_steps_is_accepted(hass, loaded, hall):
    await set_steps(
        hass, loaded.entry_id, [{"item": hall, "offset_minutes": 0, "action": "set_temperature", "heat_to": 68.3, "cool_to": 74}]
    )

    assert loaded.runtime_data.steps[0].heat_to == 68.3


async def test_a_thermostat_with_no_limits_is_checked_against_the_defaults(hass, loaded):
    hass.states.async_set("climate.bare", "off", {"supported_features": 1 + 128 + 256})
    step = {"item": "climate.bare", "offset_minutes": 0, "action": "turn_on"}

    await set_steps(hass, loaded.entry_id, [{**step, "temperature": 35}])

    assert await refused(hass, loaded.entry_id, [{**step, "temperature": 36}]) == "temperature_out_of_range"
