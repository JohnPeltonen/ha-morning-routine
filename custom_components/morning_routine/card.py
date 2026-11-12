"""Serves the dashboard card and tells Home Assistant to load it."""

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.morning_routine.const import DOMAIN

CARD_URL = "/morning_routine/morning-routine-card.js"
CARD_FILE = Path(__file__).parent / "www" / "morning-routine-card.js"


async def async_register_card(hass: HomeAssistant) -> None:
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD_FILE), False)])
    # The version in the address makes browsers fetch the new file after an update.
    frontend.add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
