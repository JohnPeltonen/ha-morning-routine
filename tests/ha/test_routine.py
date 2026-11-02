import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events
from support import ALARM, advance, advance_without_waiting, at, let_loop_run

from custom_components.morning_routine.clocks import GOOGLE_CLOCK, SAMSUNG_CLOCK
from custom_components.morning_routine.const import DOMAIN, EVENT_STEP_RAN
from custom_components.morning_routine.routine import Routine, item_is_allowed
from custom_components.morning_routine.rules import IgnoreReason, Step

SECOND_SCRIPT = "script.second_step"
NOT_HOME = "not_home"


def store_key(entry: MockConfigEntry) -> str:
    return f"{DOMAIN}.{entry.entry_id}"


async def configure(routine: Routine, steps: list[Step], on: bool = True) -> None:
    await routine.async_set_steps(steps)
    await routine.async_set_on(on)
    await routine.async_set_clock(GOOGLE_CLOCK)


async def set_state(hass: HomeAssistant, entity_id: str, state: str, attributes: dict | None = None) -> None:
    hass.states.async_set(entity_id, state, attributes)
    await hass.async_block_till_done()


async def test_step_runs_at_its_time_through_script_turn_on(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])

    await advance(hass, freezer, at(ALARM, minutes=-31))
    assert service_calls == []

    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert [(call.domain, call.service, dict(call.data)) for call in service_calls] == [
        ("script", "turn_on", {"entity_id": labeled_script})
    ]


async def test_event_is_fired_with_result(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    events = async_capture_events(hass, EVENT_STEP_RAN)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert [event.data for event in events] == [
        {"routine": entry.entry_id, "step": -30, "item": labeled_script, "result": "started"}
    ]
    assert routine.last_result is not None
    assert routine.last_result["result"] == "started"


async def test_scene_and_automation_use_their_own_services(
    hass, freezer, entry, phone, add_item, service_calls, start_routine
):
    scene = add_item("scene.test_scene")
    automation = add_item("automation.test_automation")
    routine = await start_routine(entry)
    await configure(routine, [Step(scene, -30), Step(automation, -20)])

    await advance(hass, freezer, at(ALARM, minutes=-30))
    await advance(hass, freezer, at(ALARM, minutes=-20))

    assert [(call.domain, call.service, dict(call.data)) for call in service_calls] == [
        ("scene", "turn_on", {"entity_id": scene}),
        ("automation", "trigger", {"entity_id": automation}),
    ]


async def test_ran_is_saved_before_the_service_is_called(
    hass, hass_storage, freezer, entry, phone, labeled_script, start_routine
):
    saved_at_call_time: list[list[str]] = []

    async def record(call: ServiceCall) -> None:
        alarms = hass_storage[store_key(entry)]["data"]["state"]["alarms"]
        saved_at_call_time.append(alarms[0]["ran"])

    hass.services.async_register("script", "turn_on", record)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert saved_at_call_time == [[labeled_script]]


async def test_failed_step_is_recorded_and_next_step_still_runs(
    hass, freezer, entry, phone, labeled_script, add_item, start_routine
):
    second = add_item(SECOND_SCRIPT)
    called: list[str] = []

    async def fail_for_first(call: ServiceCall) -> None:
        called.append(call.data["entity_id"])
        if call.data["entity_id"] == labeled_script:
            raise HomeAssistantError("the script is broken")

    hass.services.async_register("script", "turn_on", fail_for_first)
    events = async_capture_events(hass, EVENT_STEP_RAN)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30), Step(second, -30)])

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert called == [labeled_script, second]
    assert [(event.data["item"], event.data["result"]) for event in events] == [
        (labeled_script, "failed"),
        (second, "started"),
    ]


async def test_missing_service_is_recorded_as_failed(
    hass, freezer, entry, phone, labeled_script, start_routine
):
    events = async_capture_events(hass, EVENT_STEP_RAN)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert [event.data["result"] for event in events] == ["failed"]
    assert routine.last_result is not None
    assert routine.last_result["error"]


# Review Focus 1


async def test_tracker_blip_at_step_time_uses_last_real_location(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])

    await advance(hass, freezer, at(ALARM, minutes=-31))
    await set_state(hass, phone.tracker_id, "unavailable")
    await advance(hass, freezer, at(ALARM, minutes=-30))
    await set_state(hass, phone.tracker_id, "unknown")

    assert len(service_calls) == 1


async def test_not_home_blocks_and_coming_home_catches_up(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])
    await advance(hass, freezer, at(ALARM, minutes=-60))
    await set_state(hass, phone.tracker_id, NOT_HOME)

    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert service_calls == []

    await advance(hass, freezer, at(ALARM, minutes=-15))
    await set_state(hass, phone.tracker_id, "home")
    assert len(service_calls) == 1


async def test_coming_home_after_the_alarm_starts_nothing(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])
    await advance(hass, freezer, at(ALARM, minutes=-60))
    await set_state(hass, phone.tracker_id, NOT_HOME)

    await advance(hass, freezer, at(ALARM, minutes=1))
    await set_state(hass, phone.tracker_id, "home")

    assert service_calls == []


# Review Focus 2


async def test_restart_doesnt_repeat_a_step_that_ran(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1
    first.async_stop()

    await advance(hass, freezer, at(ALARM, minutes=-29))
    second = await start_routine(entry)
    await advance(hass, freezer, at(ALARM, minutes=-20))

    assert len(service_calls) == 1
    assert second.steps == [Step(labeled_script, -30)]
    assert second.current_alarm == ALARM


async def test_restart_runs_a_step_missed_while_down_if_under_five_minutes(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    first.async_stop()

    freezer.move_to(at(ALARM, minutes=-28))
    await start_routine(entry)

    assert len(service_calls) == 1


async def test_reload_starts_nothing_by_itself(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    first.async_stop()

    await advance(hass, freezer, at(ALARM, minutes=-45))
    await start_routine(entry)
    assert service_calls == []

    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1


async def test_last_location_survives_restart_while_tracker_unavailable(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    first.async_stop()
    await set_state(hass, phone.tracker_id, "unavailable")

    await advance(hass, freezer, at(ALARM, minutes=-45))
    await start_routine(entry)
    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert len(service_calls) == 1


async def test_restart_keeps_steps_dropped_while_running(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, 0)])
    await advance(hass, freezer, at(ALARM, minutes=-1))
    await set_state(hass, phone.tracker_id, NOT_HOME)
    await advance(hass, freezer, ALARM)
    assert service_calls == []

    await advance(hass, freezer, at(ALARM, seconds=20))
    await set_state(hass, phone.tracker_id, "home")
    assert service_calls == []
    first.async_stop()

    freezer.move_to(at(ALARM, minutes=1))
    await start_routine(entry)

    assert service_calls == []


async def test_phone_home_during_downtime_doesnt_start_a_step_at_restart(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    await advance(hass, freezer, at(ALARM, minutes=-60))
    await set_state(hass, phone.tracker_id, NOT_HOME)
    await advance(hass, freezer, at(ALARM, minutes=-30))
    first.async_stop()

    await set_state(hass, phone.tracker_id, "home")
    freezer.move_to(at(ALARM, minutes=-28))
    second = await start_routine(entry)
    await advance(hass, freezer, at(ALARM, minutes=-20))

    assert service_calls == []
    assert second.current_alarm == ALARM


async def test_alarm_first_seen_after_its_time_runs_nothing(
    hass, freezer, entry, phone, labeled_script, add_item, service_calls, start_routine
):
    second = add_item(SECOND_SCRIPT)
    third = add_item("script.third_step")
    routine = await start_routine(entry)
    await routine.async_set_steps([Step(labeled_script, -30), Step(second, 0), Step(third, 10)])
    await routine.async_set_on(True)

    await advance(hass, freezer, at(ALARM, seconds=6))
    await routine.async_set_clock(GOOGLE_CLOCK)
    await advance(hass, freezer, at(ALARM, minutes=11))

    assert service_calls == []


async def test_failed_load_starts_clean(
    hass, hass_storage, caplog, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    hass_storage[store_key(entry)] = {
        "version": 1,
        "minor_version": 1,
        "key": store_key(entry),
        "data": {
            "state": {
                "alarms": [{"time": ALARM.isoformat()}],
                "current": 0,
                "skip_next": False,
                "last_location": "home",
                "last_ignored": None,
            },
            "steps": [],
            "is_on": True,
            "clock": GOOGLE_CLOCK,
            "reported_packages": [],
        },
    }

    with caplog.at_level(logging.ERROR):
        routine = await start_routine(entry)

    assert "can't be read" in caplog.text
    assert routine.is_on is False
    assert routine.clock is None
    assert routine.current_alarm is None
    assert service_calls == []

    await configure(routine, [Step(labeled_script, -30)])
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1


async def test_settings_change_records_drops(
    hass, hass_storage, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)], on=False)
    # The clock moves without firing timers, so only the settings change can record the drop.
    freezer.move_to(at(ALARM, seconds=20))

    await routine.async_set_on(True)

    alarms = hass_storage[store_key(entry)]["data"]["state"]["alarms"]
    assert alarms[0]["dropped"] == [labeled_script]
    assert service_calls == []


# Review Focus 3


async def test_sensor_unavailable_60_seconds_cancels_then_same_time_returns(
    hass, freezer, entry, phone, labeled_script, add_item, service_calls, start_routine
):
    second = add_item(SECOND_SCRIPT)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30), Step(second, -10)])
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1

    await advance(hass, freezer, at(ALARM, minutes=-20))
    await set_state(hass, phone.sensor_id, "unavailable")
    await advance(hass, freezer, at(ALARM, minutes=-20, seconds=60))
    assert routine.current_alarm is None

    await advance(hass, freezer, at(ALARM, minutes=-18))
    await set_state(hass, phone.sensor_id, ALARM.isoformat(), {"Package": GOOGLE_CLOCK})
    assert routine.current_alarm == ALARM
    await advance(hass, freezer, at(ALARM, minutes=-10))

    assert [call.data["entity_id"] for call in service_calls] == [labeled_script, second]


async def test_sensor_unavailable_59_seconds_changes_nothing(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -10)])

    await advance(hass, freezer, at(ALARM, minutes=-20))
    await set_state(hass, phone.sensor_id, "unavailable")
    await advance(hass, freezer, at(ALARM, minutes=-20, seconds=59))
    await set_state(hass, phone.sensor_id, ALARM.isoformat(), {"Package": GOOGLE_CLOCK})
    await advance(hass, freezer, at(ALARM, minutes=-19))
    assert routine.current_alarm == ALARM

    await advance(hass, freezer, at(ALARM, minutes=-10))
    assert len(service_calls) == 1


# Review Focus 5


async def test_item_without_label_doesnt_run(
    hass, freezer, entry, phone, add_item, service_calls, start_routine
):
    unlabeled = add_item("script.no_label", labeled=False)
    routine = await start_routine(entry)
    await configure(routine, [Step(unlabeled, -30)])

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert service_calls == []
    assert not item_is_allowed(hass, unlabeled)


async def test_deleted_item_doesnt_run_and_others_do(
    hass, freezer, entry, phone, labeled_script, add_item, service_calls, start_routine
):
    second = add_item(SECOND_SCRIPT)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30), Step(second, -30)])
    er.async_get(hass).async_remove(labeled_script)
    await hass.async_block_till_done()

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert [call.data["entity_id"] for call in service_calls] == [second]
    assert [step.item for step in routine.steps] == [labeled_script, second]


async def test_item_runs_when_label_comes_back_before_alarm(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])
    registry = er.async_get(hass)
    labels = set(registry.async_get(labeled_script).labels)
    registry.async_update_entity(labeled_script, labels=set())
    await hass.async_block_till_done()

    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert service_calls == []

    await advance(hass, freezer, at(ALARM, minutes=-20))
    registry.async_update_entity(labeled_script, labels=labels)
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_sensor_entity_missing_at_start_doesnt_fail_setup(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    hass.states.async_remove(phone.sensor_id)
    hass.states.async_remove(phone.tracker_id)
    routine = await start_routine(entry)
    assert routine.current_alarm is None

    await configure(routine, [Step(labeled_script, -30)])
    await set_state(hass, phone.sensor_id, ALARM.isoformat(), {"Package": GOOGLE_CLOCK})
    await set_state(hass, phone.tracker_id, "home")
    assert routine.current_alarm == ALARM

    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1


async def test_changing_the_clock_drops_old_clocks_alarm(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])
    assert routine.current_alarm == ALARM

    await routine.async_set_clock(SAMSUNG_CLOCK)

    assert routine.current_alarm is None
    assert routine.last_ignored is not None
    assert routine.last_ignored.reason is IgnoreReason.WRONG_APP
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert service_calls == []


async def test_reported_packages_appear_in_clock_options(
    hass, entry, phone, start_routine
):
    routine = await start_routine(entry)
    await set_state(hass, phone.sensor_id, ALARM.isoformat(), {"Package": "com.example.alarm"})

    assert routine.clock_options["com.example.alarm"] == "com.example.alarm"
    assert GOOGLE_CLOCK in routine.clock_options
    assert SAMSUNG_CLOCK not in routine.clock_options


async def test_listeners_hear_about_changes_until_removed(hass, entry, phone, start_routine):
    routine = await start_routine(entry)
    heard: list[bool] = []
    remove = routine.add_listener(lambda: heard.append(routine.is_on))

    await routine.async_set_on(True)
    remove()
    await routine.async_set_on(False)

    assert heard == [True]


# Fix round 1


async def test_long_step_doesnt_hold_up_tracker_or_next_step(
    hass, hass_storage, freezer, entry, phone, labeled_script, add_item, start_routine
):
    second = add_item(SECOND_SCRIPT)
    release = asyncio.Event()
    started: list[str] = []

    async def hold_first(call: ServiceCall) -> None:
        started.append(call.data["entity_id"])
        if call.data["entity_id"] == labeled_script:
            await release.wait()

    hass.services.async_register("script", "turn_on", hold_first)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30), Step(second, -30)])
    try:
        await advance_without_waiting(hass, freezer, at(ALARM, minutes=-30))
        assert started == [labeled_script, second]

        hass.states.async_set(phone.tracker_id, NOT_HOME)
        await let_loop_run()
        assert hass_storage[store_key(entry)]["data"]["state"]["last_location"] == NOT_HOME
        async with asyncio.timeout(5):
            await routine.async_set_on(False)
        assert routine.is_on is False
    finally:
        release.set()
    await hass.async_block_till_done()


async def test_step_setting_its_own_switch_doesnt_deadlock(
    hass, freezer, entry, phone, labeled_script, start_routine
):
    called: list[str] = []
    routine = await start_routine(entry)

    async def turn_routine_off(call: ServiceCall) -> None:
        called.append(call.data["entity_id"])
        await routine.async_set_on(False)

    hass.services.async_register("script", "turn_on", turn_routine_off)
    await configure(routine, [Step(labeled_script, -30)])

    # The clock moves first: asyncio.timeout counts the frozen clock, so it can't wrap the move.
    await advance_without_waiting(hass, freezer, at(ALARM, minutes=-30))
    async with asyncio.timeout(5):
        await hass.async_block_till_done()

    assert called == [labeled_script]
    assert routine.is_on is False


async def test_unexpected_exception_records_failure_and_keeps_going(
    hass, freezer, entry, phone, labeled_script, add_item, start_routine
):
    second = add_item(SECOND_SCRIPT)
    third = add_item("script.third_step")
    called: list[str] = []

    async def fail_for_first(call: ServiceCall) -> None:
        called.append(call.data["entity_id"])
        if call.data["entity_id"] == labeled_script:
            raise ValueError("not a Home Assistant error")

    hass.services.async_register("script", "turn_on", fail_for_first)
    events = async_capture_events(hass, EVENT_STEP_RAN)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30), Step(second, -30), Step(third, -20)])

    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert called == [labeled_script, second]
    await advance(hass, freezer, at(ALARM, minutes=-20))

    assert called == [labeled_script, second, third]
    assert [(event.data["item"], event.data["result"]) for event in events] == [
        (labeled_script, "failed"),
        (second, "started"),
        (third, "started"),
    ]


async def test_stop_during_a_batch_runs_nothing_more(
    hass, hass_storage, freezer, entry, phone, labeled_script, add_item, service_calls, start_routine
):
    second = add_item(SECOND_SCRIPT)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30), Step(second, -30)])
    save = routine._store.async_save
    saves = 0

    async def stop_on_third_save(data: dict) -> None:
        nonlocal saves
        saves += 1
        if saves == 3:
            routine.async_stop()
        await save(data)

    routine._store.async_save = stop_on_third_save

    await advance(hass, freezer, at(ALARM, minutes=-30))

    assert [call.data["entity_id"] for call in service_calls] == [labeled_script]
    assert saves == 3


async def test_stop_during_the_ran_save_doesnt_start_the_step(
    hass, hass_storage, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30)])
    save = routine._store.async_save
    saves = 0

    async def stop_during_the_ran_save(data: dict) -> None:
        nonlocal saves
        saves += 1
        if saves == 2:
            routine.async_stop()
        await save(data)

    routine._store.async_save = stop_during_the_ran_save

    await advance(hass, freezer, at(ALARM, minutes=-30))

    # The save was the second one: the first is the evaluation, the second records the step as run.
    assert saves == 2
    assert hass_storage[store_key(entry)]["data"]["state"]["alarms"][0]["ran"] == [labeled_script]
    assert service_calls == []
    assert routine.last_result is None


async def test_setting_changed_while_starting_doesnt_bypass_restart_rule(
    hass, hass_storage, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    first.async_stop()

    # Six minutes late: the restart rule drops it, an ordinary evaluation would run it.
    freezer.move_to(at(ALARM, minutes=-24))
    hass.set_state(CoreState.starting)
    second = await start_routine(entry)
    await second.async_set_on(True)
    await hass.async_block_till_done()
    assert service_calls == []

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert service_calls == []
    assert hass_storage[store_key(entry)]["data"]["state"]["alarms"][0]["dropped"] == [labeled_script]


async def test_startup_path_through_started_event(
    hass, caplog, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    first.async_stop()

    hass.set_state(CoreState.starting)
    with caplog.at_level(logging.ERROR):
        second = await start_routine(entry)
        assert second.current_alarm is not None
        hass.set_state(CoreState.running)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        second.async_stop()
        await hass.async_block_till_done()

    assert [record for record in caplog.records if record.levelno >= logging.ERROR] == []
    assert second.current_alarm == ALARM


async def test_phone_left_during_downtime_doesnt_start_a_step_at_restart(
    hass, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    first = await start_routine(entry)
    await configure(first, [Step(labeled_script, -30)])
    first.async_stop()

    await set_state(hass, phone.tracker_id, NOT_HOME)
    freezer.move_to(at(ALARM, minutes=-28))
    await start_routine(entry)

    assert service_calls == []


async def test_store_read_error_starts_clean(
    hass, caplog, freezer, entry, phone, labeled_script, service_calls, start_routine
):
    with (
        caplog.at_level(logging.ERROR),
        patch.object(Store, "async_load", AsyncMock(side_effect=OSError("disk trouble"))),
    ):
        routine = await start_routine(entry)

    assert "can't be read" in caplog.text
    assert routine.is_on is False
    assert routine.clock is None

    await configure(routine, [Step(labeled_script, -30)])
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert len(service_calls) == 1


async def test_failed_save_still_sets_the_next_timer(
    hass, freezer, entry, phone, labeled_script, add_item, service_calls, start_routine
):
    second = add_item(SECOND_SCRIPT)
    routine = await start_routine(entry)
    await configure(routine, [Step(labeled_script, -30), Step(second, -20)])

    # What the timer does when it fires: forget itself, then evaluate. Called directly so the
    # error comes back to the test instead of being left unretrieved in a task.
    freezer.move_to(at(ALARM, minutes=-30))
    routine._cancel_timer()
    with (
        patch.object(routine._store, "async_save", AsyncMock(side_effect=OSError("disk trouble"))),
        pytest.raises(OSError),
    ):
        await routine._async_change()
    assert service_calls == []

    await advance(hass, freezer, at(ALARM, minutes=-20))
    assert [call.data["entity_id"] for call in service_calls] == [labeled_script, second]
