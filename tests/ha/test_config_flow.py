from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry
from support import Phone

from custom_components.morning_routine.config_flow import find_tracker
from custom_components.morning_routine.const import (
    CONF_ALARM_SENSOR,
    CONF_DEVICE_ID,
    CONF_REQUIRE_ZERO_SECONDS,
    CONF_TRACKER,
    DOMAIN,
)

PHONE_STEP = "component.morning_routine.config.step.user.description"
NO_PHONES = "component.morning_routine.config.abort.no_phones"


@pytest.fixture(autouse=True)
def setup_entry_succeeds(request):
    """These tests are about the screens. Setting up the entry itself is tested with the entities.

    A test that asks for `loaded` runs against the real setup instead.
    """
    if "loaded" in request.fixturenames:
        yield
        return
    with patch("custom_components.morning_routine.async_setup_entry", new=AsyncMock(return_value=True), create=True):
        yield


def add_decoy_device(hass, name: str, platform: str, unique_id: str) -> str:
    """A device of its own whose only sensor isn't a mobile_app Next alarm sensor."""
    mobile_app = MockConfigEntry(domain="mobile_app", title=name)
    mobile_app.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mobile_app.entry_id, identifiers={("mobile_app", unique_id)}, name=name
    )
    er.async_get(hass).async_get_or_create("sensor", platform, unique_id, config_entry=mobile_app, device_id=device.id)
    return device.id


def add_second_phone(hass, name: str = "Spare Phone") -> Phone:
    mobile_app = MockConfigEntry(domain="mobile_app", title=name)
    mobile_app.add_to_hass(hass)
    slug = name.lower().replace(" ", "_")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mobile_app.entry_id,
        identifiers={("mobile_app", slug)},
        name=name,
    )
    registry = er.async_get(hass)
    sensor = registry.async_get_or_create(
        "sensor", "mobile_app", f"{slug}_next_alarm", config_entry=mobile_app, device_id=device.id
    )
    tracker = registry.async_get_or_create(
        "device_tracker", "mobile_app", slug, config_entry=mobile_app, device_id=device.id
    )
    return Phone(device_id=device.id, sensor_id=sensor.entity_id, tracker_id=tracker.entity_id)


async def start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


def offered(result) -> list[str]:
    selector = next(iter(result["data_schema"].schema.values()))
    return [option["value"] for option in selector.config["options"]]


async def translation(hass, key: str) -> str:
    return (await async_get_translations(hass, "en", "config", [DOMAIN]))[key]


async def test_lists_phones_with_the_sensor(hass, phone):
    other = add_second_phone(hass)
    # Neither of these is a phone to follow: a mobile_app sensor of another type, and a sensor from another integration.
    battery_only = add_decoy_device(hass, "Battery Only", "mobile_app", "battery-only_battery_level")
    other_integration = add_decoy_device(hass, "Other Integration", "other", "other-integration_next_alarm")

    result = await start(hass)

    assert (result["type"], result["step_id"]) == (FlowResultType.FORM, "user")
    assert sorted(offered(result)) == sorted([phone.device_id, other.device_id])
    assert battery_only not in offered(result)
    assert other_integration not in offered(result)
    labels = {o["value"]: o["label"] for o in next(iter(result["data_schema"].schema.values())).config["options"]}
    assert labels[phone.device_id] == "Test Phone"
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_creates_entry_with_sensor_tracker_and_device(hass, phone):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DEVICE_ID: phone.device_id})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ALARM_SENSOR: phone.sensor_id,
        CONF_TRACKER: phone.tracker_id,
        CONF_DEVICE_ID: phone.device_id,
    }
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == phone.device_id
    assert entry.options.get(CONF_REQUIRE_ZERO_SECONDS, True) is True


async def test_title_uses_the_linked_person(hass, phone):
    hass.states.async_set("person.other", "home", {"device_trackers": ["device_tracker.unrelated"]})
    hass.states.async_set(
        "person.test_person", "home", {"device_trackers": [phone.tracker_id], "friendly_name": "Test Person"}
    )
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DEVICE_ID: phone.device_id})

    assert result["title"] == "Test Person's morning routine"


async def test_title_falls_back_to_device_name(hass, phone):
    hass.states.async_set("person.other", "home", {"device_trackers": ["device_tracker.unrelated"]})
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DEVICE_ID: phone.device_id})

    assert result["title"] == "Test Phone's morning routine"


async def test_same_phone_twice_aborts(hass, phone):
    first = await start(hass)
    await hass.config_entries.flow.async_configure(first["flow_id"], {CONF_DEVICE_ID: phone.device_id})

    second = await start(hass)
    result = await hass.config_entries.flow.async_configure(second["flow_id"], {CONF_DEVICE_ID: phone.device_id})

    assert (result["type"], result["reason"]) == (FlowResultType.ABORT, "already_configured")
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_phone_with_sensor_turned_off_isnt_chosen_and_gets_instructions(hass, phone):
    other = add_second_phone(hass)
    er.async_get(hass).async_update_entity(phone.sensor_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)

    result = await start(hass)

    assert offered(result) == [other.device_id]
    text = await translation(hass, PHONE_STEP)
    assert text == (
        "Choose the phone whose alarms this routine should follow. If a phone isn't listed, turn on its "
        "Next alarm sensor in the Home Assistant Android app, under Settings, Companion app, Manage sensors. "
        "Make sure that sensor's Allow list is off."
    )
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_phone_without_a_tracker_shows_an_error(hass, phone):
    er.async_get(hass).async_remove(phone.tracker_id)

    result = await start(hass)
    assert offered(result) == [phone.device_id]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DEVICE_ID: phone.device_id})

    assert result["type"] is FlowResultType.FORM
    assert (result["step_id"], result["errors"]) == ("user", {"base": "no_tracker"})
    assert hass.config_entries.async_entries(DOMAIN) == []
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_sensor_turned_off_while_the_form_is_open_shows_an_error(hass, phone):
    other = add_second_phone(hass)
    result = await start(hass)
    er.async_get(hass).async_update_entity(phone.sensor_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_DEVICE_ID: phone.device_id})

    assert result["type"] is FlowResultType.FORM
    assert (result["step_id"], result["errors"]) == ("user", {"base": "phone_gone"})
    assert offered(result) == [other.device_id]
    assert hass.config_entries.async_entries(DOMAIN) == []
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_find_tracker_ignores_a_tracker_from_another_integration(hass):
    spare = add_second_phone(hass)
    registry = er.async_get(hass)
    registry.async_remove(spare.tracker_id)
    registry.async_get_or_create("device_tracker", "other", "spare-other", device_id=spare.device_id)
    assert find_tracker(hass, spare.device_id) is None


async def test_no_phones_aborts_with_instructions(hass):
    result = await start(hass)

    assert (result["type"], result["reason"]) == (FlowResultType.ABORT, "no_phones")
    text = await translation(hass, NO_PHONES)
    assert "Next alarm sensor" in text
    assert "Allow list is off" in text


async def test_options_turn_off_the_seconds_check(hass, loaded):
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert (result["type"], result["step_id"]) == (FlowResultType.FORM, "init")

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_REQUIRE_ZERO_SECONDS: False})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_REQUIRE_ZERO_SECONDS] is False
