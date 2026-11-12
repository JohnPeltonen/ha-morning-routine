"""Running light and thermostat steps."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_capture_events
from support import ALARM, advance, at

from custom_components.morning_routine.clocks import GOOGLE_CLOCK
from custom_components.morning_routine.const import DOMAIN, EVENT_STEP_RAN
from custom_components.morning_routine.routine import Routine, step_is_allowed
from custom_components.morning_routine.rules import Step


async def configure(routine: Routine, steps: list[Step]) -> None:
    await routine.async_set_steps(steps)
    await routine.async_set_on(True)
    await routine.async_set_clock(GOOGLE_CLOCK)


def sent(service_calls) -> list[tuple[str, str, dict]]:
    return [(call.domain, call.service, dict(call.data)) for call in service_calls]


async def test_a_light_step_runs_at_its_time_with_its_brightness(
    hass, freezer, entry, phone, lamp, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(lamp, -30, id="a", action="turn_on", brightness=40)])

    await advance(hass, freezer, at(ALARM, minutes=-31))
    assert service_calls == []

    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert sent(service_calls) == [("light", "turn_on", {"entity_id": lamp, "brightness_pct": 40})]


async def test_on_and_off_steps_for_one_light_each_run_once(
    hass, freezer, entry, phone, lamp, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(
        routine,
        [Step(lamp, -30, id="a", action="turn_on"), Step(lamp, 10, id="b", action="turn_off")],
    )

    await advance(hass, freezer, at(ALARM, minutes=-30))
    await advance(hass, freezer, at(ALARM, minutes=-10))
    assert sent(service_calls) == [("light", "turn_on", {"entity_id": lamp})]

    await advance(hass, freezer, at(ALARM, minutes=10))
    await advance(hass, freezer, at(ALARM, minutes=20))
    assert sent(service_calls) == [
        ("light", "turn_on", {"entity_id": lamp}),
        ("light", "turn_off", {"entity_id": lamp}),
    ]


async def test_retiming_one_step_does_not_run_the_other_again(
    hass, freezer, entry, phone, lamp, service_calls, start_routine
):
    routine = await start_routine(entry)
    on = Step(lamp, -30, id="a", action="turn_on")
    await configure(routine, [on, Step(lamp, -10, id="b", action="turn_off")])
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1

    await routine.async_set_steps([on, Step(lamp, -5, id="b", action="turn_off")])
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_a_thermostat_is_turned_on_and_then_given_its_temperature(
    hass, freezer, entry, phone, heater, service_calls, start_routine
):
    events = async_capture_events(hass, EVENT_STEP_RAN)
    routine = await start_routine(entry)
    await configure(routine, [Step(heater, -20, id="a", action="turn_on", temperature=115)])

    await advance(hass, freezer, at(ALARM, minutes=-20))

    assert sent(service_calls) == [
        ("climate", "turn_on", {"entity_id": heater}),
        ("climate", "set_temperature", {"entity_id": heater, "temperature": 115}),
    ]
    assert [event.data for event in events] == [
        {"routine": entry.entry_id, "step": -20, "item": heater, "action": "turn_on", "result": "started"}
    ]


async def test_a_range_thermostat_in_heat_mode_gets_only_heat_to(
    hass, freezer, entry, phone, hall, service_calls, start_routine
):
    hass.states.async_set(hall, "heat", {**hass.states.get(hall).attributes, "target_temp_low": None, "target_temp_high": None})
    routine = await start_routine(entry)
    await configure(routine, [Step(hall, -5, id="a", action="set_temperature", heat_to=68, cool_to=74)])

    await advance(hass, freezer, at(ALARM, minutes=-5))

    assert sent(service_calls) == [("climate", "set_temperature", {"entity_id": hall, "temperature": 68})]


async def test_a_range_thermostat_that_is_off_is_left_alone_and_the_step_is_recorded_as_failed(
    hass, freezer, entry, phone, hall, service_calls, start_routine
):
    hass.states.async_set(hall, "off", dict(hass.states.get(hall).attributes))
    events = async_capture_events(hass, EVENT_STEP_RAN)
    routine = await start_routine(entry)
    await configure(routine, [Step(hall, -5, id="a", action="set_temperature", heat_to=68, cool_to=74)])

    await advance(hass, freezer, at(ALARM, minutes=-5))

    assert service_calls == []
    assert events[0].data["result"] == "failed"
    assert "is off" in routine.last_result["error"]
    assert routine.last_result["action"] == "set_temperature"


async def test_a_second_call_is_not_sent_when_the_first_fails(
    hass: HomeAssistant, freezer, entry, phone, heater, start_routine
):
    calls: list[str] = []

    async def fail(call) -> None:
        calls.append(call.service)
        raise RuntimeError("no answer")

    async def record(call) -> None:
        calls.append(call.service)

    hass.services.async_register("climate", "turn_on", fail)
    hass.services.async_register("climate", "set_temperature", record)
    routine = await start_routine(entry)
    await configure(routine, [Step(heater, -20, id="a", action="turn_on", temperature=115)])

    await advance(hass, freezer, at(ALARM, minutes=-20))

    assert calls == ["turn_on"]
    assert routine.last_result["result"] == "failed"


async def test_a_step_whose_device_has_no_state_does_not_run(
    hass, freezer, entry, phone, lamp, service_calls, start_routine
):
    routine = await start_routine(entry)
    step = Step(lamp, -30, id="a", action="turn_on")
    await configure(routine, [step])
    hass.states.async_remove(lamp)
    await hass.async_block_till_done()

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert not step_is_allowed(hass, step)
    assert service_calls == []


async def test_a_step_that_ran_before_the_update_is_not_run_again(
    hass, hass_storage, freezer, entry, phone, labeled_script, lamp, service_calls, start_routine
):
    # What version 0.2.0 saved: steps with three keys, and the item recorded as ran.
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1
    first.async_stop()
    saved = hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]
    assert saved["steps"] == [{"item": labeled_script, "offset_minutes": -30, "enabled": True}]
    assert saved["state"]["alarms"][0]["ran"] == [labeled_script]

    await advance(hass, freezer, at(ALARM, minutes=-29))
    second = await start_routine(entry)
    await second.async_set_steps([Step(labeled_script, -30), Step(lamp, -25, id="a", action="turn_on")])
    await advance(hass, freezer, at(ALARM, minutes=-25))

    assert sent(service_calls)[1:] == [("light", "turn_on", {"entity_id": lamp})]
