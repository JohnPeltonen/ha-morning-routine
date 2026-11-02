"""Setup screens: choose a phone. The options screen has the :00 seconds setting."""

from typing import Any

import probatio
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from custom_components.morning_routine.const import CONF_ALARM_SENSOR, CONF_DEVICE_ID, CONF_REQUIRE_ZERO_SECONDS, CONF_TRACKER, DOMAIN

OPTIONS_SCHEMA = probatio.Schema({probatio.Required(CONF_REQUIRE_ZERO_SECONDS, default=True): bool})


def find_alarm_sensors(hass: HomeAssistant) -> dict[str, str]:
    """Device id to entity id, for every phone whose Next alarm sensor is turned on."""
    sensors: dict[str, str] = {}
    for entity in er.async_get(hass).entities.values():
        if (
            entity.platform == "mobile_app"
            and entity.domain == "sensor"
            and entity.unique_id.endswith("_next_alarm")
            and entity.device_id
            and not entity.disabled
        ):
            sensors[entity.device_id] = entity.entity_id
    return sensors


def find_tracker(hass: HomeAssistant, device_id: str) -> str | None:
    for entity in er.async_entries_for_device(er.async_get(hass), device_id):
        if entity.platform == "mobile_app" and entity.domain == "device_tracker":
            return entity.entity_id
    return None


def phone_name(hass: HomeAssistant, device_id: str) -> str:
    device = dr.async_get(hass).async_get(device_id)
    return (device.name_by_user or device.name or device_id) if device else device_id


def routine_title(hass: HomeAssistant, device_id: str, tracker: str) -> str:
    for person in hass.states.async_all("person"):
        if tracker in person.attributes.get("device_trackers", []):
            return f"{person.name}'s morning routine"
    return f"{phone_name(hass, device_id)}'s morning routine"


class MorningRoutineConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MorningRoutineOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        sensors = find_alarm_sensors(self.hass)
        if not sensors:
            return self.async_abort(reason="no_phones")

        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            if device_id not in sensors:
                # The sensor was turned off while the form was open.
                errors["base"] = "phone_gone"
            elif (tracker := find_tracker(self.hass, device_id)) is None:
                errors["base"] = "no_tracker"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=routine_title(self.hass, device_id, tracker),
                    data={CONF_ALARM_SENSOR: sensors[device_id], CONF_TRACKER: tracker, CONF_DEVICE_ID: device_id},
                )

        options = [
            SelectOptionDict(value=device_id, label=phone_name(self.hass, device_id))
            for device_id in sorted(sensors, key=lambda device_id: phone_name(self.hass, device_id).lower())
        ]
        selector = SelectSelector(SelectSelectorConfig(options=options))
        schema = probatio.Schema({probatio.Required(CONF_DEVICE_ID): selector})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class MorningRoutineOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_REQUIRE_ZERO_SECONDS, True)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, {CONF_REQUIRE_ZERO_SECONDS: current}),
        )
