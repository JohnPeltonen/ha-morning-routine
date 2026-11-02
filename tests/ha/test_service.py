import pytest
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.setup import async_setup_component
from support import ALARM, advance, at

from custom_components.morning_routine.clocks import GOOGLE_CLOCK
from custom_components.morning_routine.const import DOMAIN
from custom_components.morning_routine.rules import Step


async def set_steps(hass, entry_id: str, steps: list, context: Context | None = None) -> None:
    await hass.services.async_call(
        DOMAIN, "set_steps", {"config_entry_id": entry_id, "steps": steps}, blocking=True, context=context
    )
    await hass.async_block_till_done()


async def test_set_steps_saves_and_schedules(
    hass, hass_storage, freezer, loaded, labeled_script, service_calls
):
    routine = loaded.runtime_data
    await routine.async_set_clock(GOOGLE_CLOCK)
    await routine.async_set_on(True)

    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    assert routine.steps == [Step(labeled_script, -30, True)]
    saved = hass_storage[f"{DOMAIN}.{loaded.entry_id}"]["data"]["steps"]
    assert saved == [{"item": labeled_script, "offset_minutes": -30, "enabled": True}]
    assert routine._timer is not None
    await advance(hass, freezer, at(ALARM, minutes=-30))
    assert [call.data["entity_id"] for call in service_calls] == [labeled_script]


async def test_set_steps_enabled_can_be_turned_off(hass, loaded, labeled_script):
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": 5, "enabled": False}])

    assert loaded.runtime_data.steps == [Step(labeled_script, 5, False)]


async def test_set_steps_accepts_the_edges_of_the_offset_range(hass, loaded, labeled_script, add_item):
    other = add_item("script.other_step")

    await set_steps(
        hass,
        loaded.entry_id,
        [{"item": labeled_script, "offset_minutes": -720}, {"item": other, "offset_minutes": 720}],
    )

    assert [step.offset_minutes for step in loaded.runtime_data.steps] == [-720, 720]


async def test_set_steps_with_an_empty_list_clears_the_steps(hass, loaded, labeled_script):
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    await set_steps(hass, loaded.entry_id, [])

    assert loaded.runtime_data.steps == []


async def test_set_steps_refuses_unlabeled_item(hass, loaded, labeled_script, add_item):
    unlabeled = add_item("script.no_label", labeled=False)
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    with pytest.raises(ServiceValidationError):
        await set_steps(
            hass,
            loaded.entry_id,
            [{"item": labeled_script, "offset_minutes": -10}, {"item": unlabeled, "offset_minutes": -5}],
        )

    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]


async def test_set_steps_refuses_other_domains(hass, loaded, labeled_script):
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    with pytest.raises(ServiceValidationError):
        await set_steps(hass, loaded.entry_id, [{"item": "light.test", "offset_minutes": -5}])

    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]


async def test_set_steps_refuses_duplicate_items(hass, loaded, labeled_script):
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    with pytest.raises(ServiceValidationError):
        await set_steps(
            hass,
            loaded.entry_id,
            [{"item": labeled_script, "offset_minutes": -10}, {"item": labeled_script, "offset_minutes": -5}],
        )

    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]


@pytest.mark.parametrize("offset", [721, -721, "5", 1.5, True, None])
async def test_set_steps_refuses_offset_out_of_range(hass, loaded, labeled_script, offset):
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    with pytest.raises(ServiceValidationError):
        await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": offset}])

    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]


@pytest.mark.parametrize(
    "bad_step",
    [
        "script.test_step",
        {"offset_minutes": 5},
        {"item": 5, "offset_minutes": 5},
        {"item": "script.test_step"},
        {"item": "script.test_step", "offset_minutes": 5, "enabled": "yes"},
        {"item": "script.test_step", "offset_minutes": 5, "extra": 1},
    ],
)
async def test_set_steps_refuses_malformed_steps(hass, loaded, labeled_script, bad_step):
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    with pytest.raises(ServiceValidationError):
        await set_steps(hass, loaded.entry_id, [bad_step])

    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]


async def test_set_steps_refuses_something_that_is_not_a_list(hass, loaded):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_steps", {"config_entry_id": loaded.entry_id, "steps": {"item": "script.x"}}, blocking=True
        )


async def test_set_steps_refuses_an_unknown_entry(hass):
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError):
        await set_steps(hass, "not-an-entry", [])


async def test_set_steps_refuses_an_entry_that_is_not_loaded(hass, loaded):
    await hass.config_entries.async_unload(loaded.entry_id)

    with pytest.raises(ServiceValidationError):
        await set_steps(hass, loaded.entry_id, [])


async def test_set_steps_refused_for_non_admin(hass, loaded, labeled_script, household_member):
    with pytest.raises(Unauthorized):
        await set_steps(
            hass,
            loaded.entry_id,
            [{"item": labeled_script, "offset_minutes": -30}],
            Context(user_id=household_member.id),
        )

    assert loaded.runtime_data.steps == []


async def test_set_steps_with_passed_time_runs_right_away(
    hass, freezer, loaded, labeled_script, service_calls
):
    routine = loaded.runtime_data
    await routine.async_set_clock(GOOGLE_CLOCK)
    await routine.async_set_on(True)
    freezer.move_to(at(ALARM, minutes=-20))

    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    assert [call.data["entity_id"] for call in service_calls] == [labeled_script]
