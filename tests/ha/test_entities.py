from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.select import DATA_COMPONENT as SELECT_DATA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from support import ALARM, advance, at, entity_id

from custom_components.morning_routine.clocks import GOOGLE_CLOCK
from custom_components.morning_routine.const import CONF_REQUIRE_ZERO_SECONDS, DOMAIN
from custom_components.morning_routine.rules import Step

GOOGLE_NAME = "Google Clock"
SAMSUNG_NAME = "Samsung Clock"


async def call(hass, domain: str, service: str, target: str, context: Context | None = None, **data) -> None:
    await hass.services.async_call(domain, service, {"entity_id": target, **data}, blocking=True, context=context)
    await hass.async_block_till_done()


async def choose_google(hass, entry) -> None:
    await call(hass, "select", "select_option", entity_id(hass, entry, "select", "clock"), option=GOOGLE_NAME)


async def test_entities_are_created_on_one_device(hass, loaded):
    entities = er.async_entries_for_config_entry(er.async_get(hass), loaded.entry_id)

    assert {(entity.domain, entity.unique_id.removeprefix(f"{loaded.entry_id}_")) for entity in entities} == {
        ("switch", "routine"),
        ("switch", "skip_next_alarm"),
        ("select", "clock"),
        ("sensor", "current_alarm"),
        ("sensor", "last_ignored_entry"),
    }
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), loaded.entry_id)
    assert len(devices) == 1
    assert {entity.device_id for entity in entities} == {devices[0].id}
    assert {entity.domain for entity in entities if entity.entity_category is not None} == {"sensor"}


async def test_routine_starts_off_with_no_clock(hass, loaded):
    assert hass.states.get(entity_id(hass, loaded, "switch", "routine")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, loaded, "switch", "skip_next_alarm")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, loaded, "select", "clock")).state == STATE_UNKNOWN
    assert loaded.runtime_data.clock is None


async def test_routine_switch_changes_the_routine(hass, hass_storage, loaded):
    switch = entity_id(hass, loaded, "switch", "routine")

    await call(hass, "switch", "turn_on", switch)
    assert hass.states.get(switch).state == STATE_ON
    assert loaded.runtime_data.is_on is True
    assert hass_storage[f"{DOMAIN}.{loaded.entry_id}"]["data"]["is_on"] is True

    await call(hass, "switch", "turn_off", switch)
    assert hass.states.get(switch).state == STATE_OFF
    assert loaded.runtime_data.is_on is False


async def test_skip_switch_turns_itself_off_when_alarm_goes_off(hass, freezer, loaded):
    skip = entity_id(hass, loaded, "switch", "skip_next_alarm")
    await choose_google(hass, loaded)

    await call(hass, "switch", "turn_on", skip)
    assert hass.states.get(skip).state == STATE_ON

    await advance(hass, freezer, ALARM)
    assert hass.states.get(skip).state == STATE_OFF


async def test_select_lists_samsung_clock_on_a_samsung_phone(hass, phone, loaded):
    select = entity_id(hass, loaded, "select", "clock")
    assert hass.states.get(select).attributes["options"] == [GOOGLE_NAME]

    dr.async_get(hass).async_update_device(phone.device_id, manufacturer="Samsung")
    await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(select).attributes["options"] == [GOOGLE_NAME, SAMSUNG_NAME]


async def test_select_saves_the_chosen_clock_as_a_package(hass, hass_storage, loaded):
    select = entity_id(hass, loaded, "select", "clock")

    await choose_google(hass, loaded)

    assert hass.states.get(select).state == GOOGLE_NAME
    assert loaded.runtime_data.clock == GOOGLE_CLOCK
    assert hass_storage[f"{DOMAIN}.{loaded.entry_id}"]["data"]["clock"] == GOOGLE_CLOCK


async def test_select_with_a_name_that_has_no_package_changes_nothing(hass, loaded):
    select = entity_id(hass, loaded, "select", "clock")
    await choose_google(hass, loaded)

    with pytest.raises(ServiceValidationError):
        await hass.data[SELECT_DATA].get_entity(select).async_select_option("Not a clock")

    assert loaded.runtime_data.clock == GOOGLE_CLOCK


async def test_current_alarm_sensor_follows_the_routine(hass, phone, loaded):
    sensor = entity_id(hass, loaded, "sensor", "current_alarm")
    assert hass.states.get(sensor).state == STATE_UNKNOWN

    await choose_google(hass, loaded)
    assert hass.states.get(sensor).state == ALARM.isoformat()

    earlier = at(ALARM, hours=-1)
    hass.states.async_set(phone.sensor_id, earlier.isoformat(), {"Package": GOOGLE_CLOCK})
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == earlier.isoformat()


async def test_last_ignored_sensor_has_package_and_reason(hass, loaded):
    state = hass.states.get(entity_id(hass, loaded, "sensor", "last_ignored_entry"))

    assert state.state == ALARM.isoformat()
    assert state.attributes["package"] == GOOGLE_CLOCK
    assert state.attributes["reason"] == "no_clock"


async def test_last_ignored_sensor_is_empty_before_anything_is_ignored(hass, entry, phone):
    hass.states.async_set(phone.sensor_id, "unavailable")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id(hass, entry, "sensor", "last_ignored_entry"))
    assert state.state == STATE_UNKNOWN
    assert "reason" not in state.attributes

    await hass.config_entries.async_unload(entry.entry_id)


async def test_turning_off_seconds_check_picks_up_alarm_on_the_sensor(hass, phone, loaded):
    sensor = entity_id(hass, loaded, "sensor", "current_alarm")
    ignored = entity_id(hass, loaded, "sensor", "last_ignored_entry")
    await choose_google(hass, loaded)
    off_the_minute = ALARM + timedelta(seconds=30)
    hass.states.async_set(phone.sensor_id, off_the_minute.isoformat(), {"Package": GOOGLE_CLOCK})
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == STATE_UNKNOWN
    assert hass.states.get(ignored).attributes["reason"] == "not_on_the_minute"

    hass.config_entries.async_update_entry(loaded, options={CONF_REQUIRE_ZERO_SECONDS: False})
    await hass.async_block_till_done()

    assert hass.states.get(sensor).state == off_the_minute.isoformat()


async def test_turning_on_seconds_check_stops_following_a_rejected_entry(
    hass, freezer, phone, loaded, labeled_script, service_calls
):
    sensor = entity_id(hass, loaded, "sensor", "current_alarm")
    off_the_minute = ALARM + timedelta(seconds=3)
    hass.config_entries.async_update_entry(loaded, options={CONF_REQUIRE_ZERO_SECONDS: False})
    hass.states.async_set(phone.sensor_id, off_the_minute.isoformat(), {"Package": GOOGLE_CLOCK})
    await choose_google(hass, loaded)
    await loaded.runtime_data.async_set_steps([Step(labeled_script, -30)])
    await loaded.runtime_data.async_set_on(True)
    assert hass.states.get(sensor).state == off_the_minute.isoformat()

    hass.config_entries.async_update_entry(loaded, options={CONF_REQUIRE_ZERO_SECONDS: True})
    await hass.async_block_till_done()
    assert hass.states.get(sensor).state == STATE_UNKNOWN
    await advance(hass, freezer, at(off_the_minute, minutes=-30))

    assert service_calls == []


async def test_non_admin_can_use_the_switches(hass, loaded, household_member):
    context = Context(user_id=household_member.id)
    routine = entity_id(hass, loaded, "switch", "routine")
    skip = entity_id(hass, loaded, "switch", "skip_next_alarm")
    clock = entity_id(hass, loaded, "select", "clock")

    await call(hass, "switch", "turn_on", routine, context)
    assert hass.states.get(routine).state == STATE_ON
    await call(hass, "switch", "turn_off", routine, context)
    assert hass.states.get(routine).state == STATE_OFF

    await call(hass, "switch", "turn_on", skip, context)
    assert hass.states.get(skip).state == STATE_ON
    await call(hass, "switch", "turn_off", skip, context)
    assert hass.states.get(skip).state == STATE_OFF

    await call(hass, "select", "select_option", clock, context, option=GOOGLE_NAME)
    assert hass.states.get(clock).state == GOOGLE_NAME


async def test_diagnostics_include_the_last_result(
    hass, hass_client, hass_admin_user, freezer, loaded, labeled_script, service_calls
):
    assert await async_setup_component(hass, "diagnostics", {})
    # The clock is frozen in the future, so the fixture's 30 minute token would already be expired.
    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, "https://example.test", access_token_expiration=timedelta(days=1)
    )
    token = hass.auth.async_create_access_token(refresh_token)
    routine = loaded.runtime_data
    await choose_google(hass, loaded)
    await routine.async_set_steps([Step(labeled_script, -30)])
    await routine.async_set_on(True)
    await advance(hass, freezer, at(ALARM, minutes=-30))

    client = await hass_client(token)
    response = await client.get(f"/api/diagnostics/config_entry/{loaded.entry_id}")

    assert response.status == 200
    data = (await response.json())["data"]
    assert data["last_result"]["item"] == labeled_script
    assert data["last_result"]["result"] == "started"
    assert data["steps"] == [{"item": labeled_script, "offset_minutes": -30, "enabled": True}]
    assert data["clock"] == GOOGLE_CLOCK
    assert data["state"]["alarms"][0]["ran"] == [labeled_script]


async def test_diagnostics_show_home_or_not_home_but_never_a_zone_name(
    hass, hass_client, hass_admin_user, phone, loaded
):
    assert await async_setup_component(hass, "diagnostics", {})
    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, "https://example.test", access_token_expiration=timedelta(days=1)
    )
    client = await hass_client(hass.auth.async_create_access_token(refresh_token))
    url = f"/api/diagnostics/config_entry/{loaded.entry_id}"

    async def location() -> str | None:
        return (await (await client.get(url)).json())["data"]["state"]["last_location"]

    assert await location() == "home"

    hass.states.async_set(phone.tracker_id, "Some Faraway Place")
    await hass.async_block_till_done()
    assert await location() == "not_home"
    assert "Faraway" not in await (await client.get(url)).text()


async def test_unload_cancels_timers_and_listeners(hass, loaded, labeled_script):
    routine = loaded.runtime_data
    await choose_google(hass, loaded)
    await routine.async_set_steps([Step(labeled_script, -30)])
    await routine.async_set_on(True)
    assert routine._timer is not None
    assert routine._listeners

    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.async_block_till_done()

    assert routine._timer is None
    assert routine._no_alarm_timer is None
    assert routine._listeners == []
    assert routine._unsubs == []
    assert hass.states.get(entity_id(hass, loaded, "switch", "routine")).state == STATE_UNAVAILABLE


async def test_removing_the_entry_removes_its_store(hass, hass_storage, loaded):
    await call(hass, "switch", "turn_on", entity_id(hass, loaded, "switch", "routine"))
    key = f"{DOMAIN}.{loaded.entry_id}"
    assert key in hass_storage

    await hass.config_entries.async_remove(loaded.entry_id)
    await hass.async_block_till_done()

    assert key not in hass_storage


async def test_failed_platform_setup_stops_the_routine(hass, entry):
    with patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=RuntimeError("boom")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    routine = entry.runtime_data
    assert routine._stopped
    assert routine._unsubs == []
    assert routine._timer is None
