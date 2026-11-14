from homeassistant.components import frontend
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.morning_routine.card import CARD_URL
from custom_components.morning_routine.const import DOMAIN


async def test_the_card_file_is_served(hass, hass_client, loaded):
    response = await (await hass_client()).get("/morning_routine/morning-routine-card.js")

    assert response.status == 200
    assert "morning-routine-card" in await response.text()


async def test_home_assistant_is_told_to_load_the_card(hass, loaded):
    urls = hass.data[frontend.DATA_EXTRA_MODULE_URL].urls

    assert "/morning_routine/morning-routine-card.js?v=0.4.1" in urls


async def test_a_second_routine_does_not_register_the_card_twice(hass, loaded):
    second = MockConfigEntry(domain=DOMAIN, title="Second routine", data=dict(loaded.data))
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    urls = [url for url in hass.data[frontend.DATA_EXTRA_MODULE_URL].urls if url.startswith(CARD_URL)]
    assert len(urls) == 1
    await hass.config_entries.async_unload(second.entry_id)
