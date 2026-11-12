import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import CLIENT_ID

from custom_components.morning_routine.clocks import GOOGLE_CLOCK
from custom_components.morning_routine.rules import Step
from custom_components.morning_routine.view import build_view


@pytest.fixture
async def member_client(hass, household_member, hass_ws_client):
    """A WebSocket connection logged in as an account that is not an administrator."""
    refresh_token = await hass.auth.async_create_refresh_token(household_member, CLIENT_ID)
    return await hass_ws_client(hass, hass.auth.async_create_access_token(refresh_token))


async def call(client, **message) -> dict:
    """Send a command and return its result, skipping events that arrive first."""
    await client.send_json_auto_id(message)
    while True:
        answer = await client.receive_json()
        if answer["type"] == "result" and answer["id"] == message["id"]:
            return answer


async def subscribe(client, entry_id: str) -> dict:
    """Subscribe and return the first view."""
    result = await call(client, type="morning_routine/subscribe", entry_id=entry_id)
    assert result["success"], result
    return (await client.receive_json())["event"]["view"]


async def event_where(client, wanted) -> dict:
    for _ in range(20):
        answer = await client.receive_json()
        if answer["type"] == "event" and wanted(answer["event"]):
            return answer["event"]
    raise AssertionError("the event never arrived")


async def test_subscribe_sends_the_view_first(hass, loaded, member_client):
    await member_client.send_json_auto_id({"type": "morning_routine/subscribe", "entry_id": loaded.entry_id})

    result = await member_client.receive_json()
    event = await member_client.receive_json()

    assert result["success"]
    assert event["id"] == result["id"]
    assert event["event"] == {"view": build_view(hass, loaded)}


async def test_subscribe_refuses_an_unknown_routine(hass, loaded, member_client):
    result = await call(member_client, type="morning_routine/subscribe", entry_id="not-an-entry")

    assert not result["success"]
    assert result["error"]["code"] == "not_found"


async def test_commands_refuse_another_integrations_entry(hass, loaded, phone, member_client):
    other = er.async_get(hass).async_get(phone.sensor_id).config_entry_id

    for command in ({"type": "morning_routine/set_steps", "steps": []}, {"type": "morning_routine/update"}):
        result = await call(member_client, entry_id=other, **command)
        assert result["error"]["code"] == "not_found"


async def test_commands_refuse_a_routine_that_is_not_loaded(hass, loaded, member_client):
    await hass.config_entries.async_unload(loaded.entry_id)

    result = await call(member_client, type="morning_routine/subscribe", entry_id=loaded.entry_id)

    assert result["error"]["code"] == "not_found"


async def test_non_admin_sets_steps_and_gets_a_new_view(hass, loaded, labeled_script, member_client):
    await subscribe(member_client, loaded.entry_id)

    await member_client.send_json_auto_id(
        {
            "type": "morning_routine/set_steps",
            "entry_id": loaded.entry_id,
            "steps": [{"item": labeled_script, "offset_minutes": -30, "enabled": True}],
        }
    )
    event = await event_where(member_client, lambda event: event["view"]["steps"])

    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]
    assert event["view"]["steps"][0]["item"] == labeled_script
    assert event["view"]["steps"][0]["offset_minutes"] == -30


async def test_set_steps_refuses_an_unlabeled_item_and_changes_nothing(
    hass, loaded, labeled_script, add_item, member_client
):
    unlabeled = add_item("script.unlabeled", labeled=False)
    await loaded.runtime_data.async_set_steps([Step(labeled_script, -30, True)])

    result = await call(
        member_client,
        type="morning_routine/set_steps",
        entry_id=loaded.entry_id,
        steps=[{"item": unlabeled, "offset_minutes": 0}],
    )

    assert not result["success"]
    assert result["error"]["translation_key"] == "item_not_allowed"
    assert "morning routine" in result["error"]["message"]
    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]


@pytest.mark.parametrize("offset", [61, -721, "5", 1.5])
async def test_set_steps_refuses_an_offset_outside_the_range(hass, loaded, labeled_script, member_client, offset):
    await loaded.runtime_data.async_set_steps([Step(labeled_script, -30, True)])

    result = await call(
        member_client,
        type="morning_routine/set_steps",
        entry_id=loaded.entry_id,
        steps=[{"item": labeled_script, "offset_minutes": offset}],
    )

    assert result["error"]["translation_key"] == "offset_out_of_range"
    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]


async def test_set_steps_refuses_something_that_is_not_a_list(hass, loaded, member_client):
    result = await call(
        member_client, type="morning_routine/set_steps", entry_id=loaded.entry_id, steps={"item": "script.x"}
    )

    assert not result["success"]
    assert loaded.runtime_data.steps == []


async def test_set_steps_keeps_a_step_whose_item_lost_its_label(
    hass, loaded, labeled_script, add_item, member_client
):
    other = add_item("script.other_step")
    await loaded.runtime_data.async_set_steps([Step(labeled_script, -30, True), Step(other, 0, True)])
    er.async_get(hass).async_update_entity(labeled_script, labels=set())

    result = await call(
        member_client,
        type="morning_routine/set_steps",
        entry_id=loaded.entry_id,
        steps=[
            {"item": labeled_script, "offset_minutes": -30, "enabled": True},
            {"item": other, "offset_minutes": 0, "enabled": False},
        ],
    )

    assert result["success"], result
    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True), Step(other, 0, False)]


async def test_non_admin_turns_the_routine_on_and_off(hass, loaded, member_client):
    assert (await call(member_client, type="morning_routine/update", entry_id=loaded.entry_id, is_on=True))["success"]
    assert loaded.runtime_data.is_on is True

    assert (await call(member_client, type="morning_routine/update", entry_id=loaded.entry_id, is_on=False))["success"]
    assert loaded.runtime_data.is_on is False


async def test_non_admin_sets_skip(hass, loaded, member_client):
    result = await call(member_client, type="morning_routine/update", entry_id=loaded.entry_id, skip_next=True)

    assert result["success"], result
    assert loaded.runtime_data.skip_next is True


async def test_non_admin_chooses_a_clock(hass, loaded, member_client):
    result = await call(member_client, type="morning_routine/update", entry_id=loaded.entry_id, clock=GOOGLE_CLOCK)

    assert result["success"], result
    assert loaded.runtime_data.clock == GOOGLE_CLOCK


async def test_update_refuses_a_clock_that_is_not_offered(hass, loaded, member_client):
    result = await call(
        member_client, type="morning_routine/update", entry_id=loaded.entry_id, clock="com.example.notaclock", is_on=True
    )

    assert result["error"]["translation_key"] == "clock_not_offered"
    assert result["error"]["message"].startswith("That clock isn't offered for this phone")
    assert loaded.runtime_data.clock is None
    assert loaded.runtime_data.is_on is False


async def test_update_refuses_a_value_of_the_wrong_type(hass, loaded, member_client):
    result = await call(member_client, type="morning_routine/update", entry_id=loaded.entry_id, is_on="yes")

    assert result["error"]["code"] == "invalid_format"
    assert loaded.runtime_data.is_on is False


async def test_two_subscribers_both_hear_a_change(hass, loaded, labeled_script, member_client, hass_ws_client):
    admin_client = await hass_ws_client(hass)
    await subscribe(member_client, loaded.entry_id)
    await subscribe(admin_client, loaded.entry_id)

    await admin_client.send_json_auto_id(
        {
            "type": "morning_routine/set_steps",
            "entry_id": loaded.entry_id,
            "steps": [{"item": labeled_script, "offset_minutes": 15}],
        }
    )

    for client in (member_client, admin_client):
        event = await event_where(client, lambda event: event["view"]["steps"])
        assert event["view"]["steps"][0]["offset_minutes"] == 15


async def test_view_is_sent_again_when_an_item_gains_the_label(hass, loaded, add_item, member_client):
    first = await subscribe(member_client, loaded.entry_id)
    assert first["items"] == [] and "no_label" in first["problems"]

    added = add_item("scene.wake_up")

    event = await event_where(member_client, lambda event: event["view"]["items"])
    assert event["view"]["items"][0]["item"] == added
    assert "no_label" not in event["view"]["problems"]


async def test_subscriber_is_told_when_the_routine_unloads(hass, loaded, member_client):
    await subscribe(member_client, loaded.entry_id)

    await hass.config_entries.async_unload(loaded.entry_id)

    assert await event_where(member_client, lambda event: "unavailable" in event) == {"unavailable": True}


async def test_unsubscribe_removes_the_listeners(hass, loaded, add_item, member_client):
    routine = loaded.runtime_data
    before = len(routine._listeners)
    await member_client.send_json_auto_id({"type": "morning_routine/subscribe", "entry_id": loaded.entry_id})
    subscription = (await member_client.receive_json())["id"]
    await member_client.receive_json()
    assert len(routine._listeners) == before + 1

    result = await call(member_client, type="unsubscribe_events", subscription=subscription)
    assert result["success"], result
    assert len(routine._listeners) == before

    # Nothing is sent for a later change: the next message is the answer to the next command.
    add_item("scene.wake_up")
    await hass.async_block_till_done()
    await member_client.send_json_auto_id({"type": "ping"})
    assert (await member_client.receive_json())["type"] == "pong"
