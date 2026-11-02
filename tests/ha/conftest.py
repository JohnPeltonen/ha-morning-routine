from collections.abc import AsyncIterator, Callable, Iterator

import pytest
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.auth.models import User
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er, label_registry as lr
from pytest_homeassistant_custom_component.common import MockConfigEntry
from support import ALARM, START, Phone

from custom_components.morning_routine.clocks import GOOGLE_CLOCK
from custom_components.morning_routine.const import (
    CONF_ALARM_SENSOR,
    CONF_DEVICE_ID,
    CONF_TRACKER,
    DOMAIN,
    LABEL_NAME,
)
from custom_components.morning_routine.routine import Routine


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let HA load the integration from custom_components."""


@pytest.fixture
def phone(hass: HomeAssistant, freezer) -> Phone:
    freezer.move_to(START)
    mobile_app = MockConfigEntry(domain="mobile_app", title="Test Phone")
    mobile_app.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mobile_app.entry_id,
        identifiers={("mobile_app", "test-phone-id")},
        name="Test Phone",
        manufacturer="Acme",
        model="Test 1",
    )
    registry = er.async_get(hass)
    sensor = registry.async_get_or_create(
        "sensor",
        "mobile_app",
        "test-phone-id_next_alarm",
        suggested_object_id="test_phone_next_alarm",
        config_entry=mobile_app,
        device_id=device.id,
    )
    tracker = registry.async_get_or_create(
        "device_tracker",
        "mobile_app",
        "test-phone-id",
        suggested_object_id="test_phone",
        config_entry=mobile_app,
        device_id=device.id,
    )
    hass.states.async_set(sensor.entity_id, ALARM.isoformat(), {"Package": GOOGLE_CLOCK})
    hass.states.async_set(tracker.entity_id, "home")
    return Phone(device_id=device.id, sensor_id=sensor.entity_id, tracker_id=tracker.entity_id)


@pytest.fixture
def entry(hass: HomeAssistant, phone: Phone) -> MockConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Phone's morning routine",
        data={
            CONF_ALARM_SENSOR: phone.sensor_id,
            CONF_TRACKER: phone.tracker_id,
            CONF_DEVICE_ID: phone.device_id,
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def loaded(hass: HomeAssistant, entry: MockConfigEntry) -> AsyncIterator[MockConfigEntry]:
    """The entry, set up for real. Unloaded again when the test ends."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield entry
    if entry.state is ConfigEntryState.LOADED:
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.fixture
async def household_member(hass: HomeAssistant, hass_admin_user: User) -> User:
    """A normal account, not an administrator. The admin comes first: the first user created is the owner."""
    user = await hass.auth.async_create_user("Household member", group_ids=[GROUP_ID_USER])
    assert not user.is_admin
    return user


@pytest.fixture
def start_routine(hass: HomeAssistant) -> Iterator[Callable]:
    """Start a Routine for an entry. Anything still running is stopped when the test ends."""
    started: list[Routine] = []

    async def start(config_entry: MockConfigEntry) -> Routine:
        routine = Routine(hass, config_entry)
        started.append(routine)
        await routine.async_start()
        await hass.async_block_till_done()
        return routine

    yield start
    for routine in started:
        routine.async_stop()


@pytest.fixture
def add_item(hass: HomeAssistant) -> Callable[..., str]:
    """Register a script, scene or automation, with the label unless told otherwise."""

    def add(item: str, labeled: bool = True) -> str:
        domain, object_id = item.split(".")
        entity = er.async_get(hass).async_get_or_create(
            domain, domain, object_id, suggested_object_id=object_id
        )
        labels = lr.async_get(hass)
        label = labels.async_get_label_by_name(LABEL_NAME) or labels.async_create(LABEL_NAME)
        if labeled:
            er.async_get(hass).async_update_entity(entity.entity_id, labels={label.label_id})
        return entity.entity_id

    return add


@pytest.fixture
def labeled_script(add_item: Callable[..., str]) -> str:
    return add_item("script.test_step")


@pytest.fixture
def service_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Record every call to the services a step can use."""
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    for domain, service in (("script", "turn_on"), ("scene", "turn_on"), ("automation", "trigger")):
        hass.services.async_register(domain, service, record)
    return calls
