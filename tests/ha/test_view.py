from datetime import timedelta

from homeassistant.helpers import entity_registry as er
from support import ALARM

from custom_components.morning_routine.clocks import GOOGLE_CLOCK
from custom_components.morning_routine.rules import Step
from custom_components.morning_routine.view import build_view


async def test_view_of_a_new_routine(hass, loaded):
    view = build_view(hass, loaded)

    assert view["entry_id"] == loaded.entry_id
    assert view["title"] == "Test Phone's morning routine"
    assert (view["is_on"], view["skip_next"], view["clock"]) == (False, False, None)
    assert view["clock_options"] == [{"package": GOOGLE_CLOCK, "name": "Google Clock"}]
    assert view["steps"] == [] and view["items"] == []
    assert view["problems"] == ["no_label", "no_clock"]
    assert (view["min_offset_minutes"], view["max_offset_minutes"]) == (-720, 60)


async def test_view_lists_steps_and_labeled_items_by_name(hass, loaded, add_item):
    zebra = add_item("script.zebra")
    apple = add_item("scene.apple")
    add_item("script.no_label", labeled=False)
    hass.states.async_set(zebra, "off", {"friendly_name": "Zebra"})
    hass.states.async_set(apple, "unknown", {"friendly_name": "Apple"})
    await loaded.runtime_data.async_set_steps([Step(zebra, -30, True)])

    view = build_view(hass, loaded)

    assert view["steps"] == [
        {"item": zebra, "name": "Zebra", "offset_minutes": -30, "enabled": True, "available": True}
    ]
    assert view["items"] == [{"item": apple, "name": "Apple"}, {"item": zebra, "name": "Zebra"}]
    assert "no_label" not in view["problems"]


async def test_view_marks_a_step_whose_item_lost_its_label(hass, loaded, labeled_script):
    await loaded.runtime_data.async_set_steps([Step(labeled_script, 0, False)])
    er.async_get(hass).async_update_entity(labeled_script, labels=set())
    await hass.async_block_till_done()

    view = build_view(hass, loaded)

    assert view["steps"][0]["available"] is False
    assert view["steps"][0]["enabled"] is False
    assert view["items"] == []


async def test_view_marks_a_step_whose_item_was_deleted(hass, loaded, labeled_script):
    await loaded.runtime_data.async_set_steps([Step(labeled_script, -30, True)])
    er.async_get(hass).async_remove(labeled_script)
    await hass.async_block_till_done()

    step = build_view(hass, loaded)["steps"][0]

    assert step["available"] is False
    assert step["name"] == labeled_script


async def test_view_names_an_item_without_a_state_from_the_registry(hass, loaded, labeled_script):
    er.async_get(hass).async_update_entity(labeled_script, name="Start the heater")

    assert build_view(hass, loaded)["items"] == [{"item": labeled_script, "name": "Start the heater"}]


async def test_view_says_the_sensor_is_missing_when_it_is_disabled(hass, loaded, phone):
    er.async_get(hass).async_update_entity(phone.sensor_id, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()

    assert "sensor_missing" in build_view(hass, loaded)["problems"]


async def test_view_says_the_sensor_is_missing_when_it_was_removed(hass, loaded, phone):
    er.async_get(hass).async_remove(phone.sensor_id)
    await hass.async_block_till_done()

    assert "sensor_missing" in build_view(hass, loaded)["problems"]


async def test_view_does_not_call_an_unavailable_sensor_a_problem(hass, loaded, phone):
    hass.states.async_set(phone.sensor_id, "unavailable")
    await hass.async_block_till_done()

    assert build_view(hass, loaded)["problems"] == ["no_label", "no_clock"]


async def test_view_says_the_sensor_is_stale_after_90_minutes(hass, freezer, loaded, phone):
    freezer.move_to(ALARM + timedelta(minutes=90))
    assert "sensor_stale" not in build_view(hass, loaded)["problems"]

    freezer.move_to(ALARM + timedelta(minutes=91))
    assert "sensor_stale" in build_view(hass, loaded)["problems"]


async def test_view_has_no_clock_problem_once_a_clock_is_chosen(hass, loaded):
    await loaded.runtime_data.async_set_clock(GOOGLE_CLOCK)

    view = build_view(hass, loaded)

    assert view["clock"] == GOOGLE_CLOCK
    assert "no_clock" not in view["problems"]
