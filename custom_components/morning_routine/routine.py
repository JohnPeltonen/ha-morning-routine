"""Connects the alarm rules to Home Assistant: listeners, timers, saving and running steps."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er, label_registry as lr
from homeassistant.helpers.event import async_track_point_in_utc_time, async_track_state_change_event
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from custom_components.morning_routine import rules
from custom_components.morning_routine.clocks import clock_options
from custom_components.morning_routine.const import (
    ALLOWED_DOMAINS,
    CONF_ALARM_SENSOR,
    CONF_DEVICE_ID,
    CONF_REQUIRE_ZERO_SECONDS,
    CONF_TRACKER,
    DOMAIN,
    EVENT_STEP_RAN,
    LABEL_NAME,
)
from custom_components.morning_routine.rules import Alarm, IgnoredEntry, RoutineState, Step

logger = logging.getLogger(__name__)

STORE_VERSION = 1
STEP_SERVICES = {
    "script": ("script", "turn_on"),
    "scene": ("scene", "turn_on"),
    "automation": ("automation", "trigger"),
}


def item_is_allowed(hass: HomeAssistant, item: str) -> bool:
    if item.split(".", 1)[0] not in ALLOWED_DOMAINS:
        return False
    registry_entry = er.async_get(hass).async_get(item)
    label = lr.async_get(hass).async_get_label_by_name(LABEL_NAME)
    return registry_entry is not None and label is not None and label.label_id in registry_entry.labels


def routine_store(hass: HomeAssistant, entry: ConfigEntry) -> Store[dict[str, Any]]:
    return Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}", atomic_writes=True)


class Routine:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._store = routine_store(hass, entry)
        self._lock = asyncio.Lock()
        self._state = RoutineState()
        self._steps: list[Step] = []
        self._on = False
        self._clock: str | None = None
        self._reported: set[str] = set()
        self._last_result: dict | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timer: CALLBACK_TYPE | None = None
        self._no_alarm_timer: CALLBACK_TYPE | None = None
        self._stopped = False
        self._started = False

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def skip_next(self) -> bool:
        return self._state.skip_next

    @property
    def clock(self) -> str | None:
        return self._clock

    @property
    def clock_options(self) -> dict[str, str]:
        device = dr.async_get(self._hass).async_get(self._entry.data.get(CONF_DEVICE_ID, ""))
        return clock_options(device.manufacturer if device else None, self._reported, self._clock)

    @property
    def current_alarm(self) -> datetime | None:
        current = self._state.current
        return None if current is None else current.time

    @property
    def last_ignored(self) -> IgnoredEntry | None:
        return self._state.last_ignored

    @property
    def steps(self) -> list[Step]:
        return list(self._steps)

    @property
    def last_result(self) -> dict | None:
        return self._last_result

    @property
    def _require_zero_seconds(self) -> bool:
        return self._entry.options.get(CONF_REQUIRE_ZERO_SECONDS, True)

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    async def async_start(self) -> None:
        await self._async_load()
        if self._hass.state is CoreState.running:
            await self._async_begin()
            return

        async def begin(_hass: HomeAssistant) -> None:
            await self._async_begin()

        self._unsubs.append(async_at_started(self._hass, begin))

    def async_stop(self) -> None:
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_timer()
        self._cancel_no_alarm_timer()

    async def async_set_on(self, on: bool) -> None:
        def change(_now: datetime) -> None:
            self._on = on

        await self._async_change(change)

    async def async_set_skip(self, on: bool) -> None:
        await self._async_change(lambda now: rules.set_skip(self._state, on, now))

    async def async_set_clock(self, package: str) -> None:
        def change(now: datetime) -> None:
            self._clock = package
            rules.change_clock(self._state)
            self._observe_current_sensor(now)

        await self._async_change(change)

    async def async_reread_sensor(self) -> None:
        await self._async_change(self._observe_current_sensor)

    async def async_set_steps(self, steps: list[Step]) -> None:
        def change(_now: datetime) -> None:
            self._steps = list(steps)

        await self._async_change(change)

    async def _async_load(self) -> None:
        try:
            data = await self._store.async_load()
            if data is None:
                return
            state = rules.state_from_dict(data["state"])
            steps = rules.steps_from_list(data["steps"])
            on = bool(data["is_on"])
            clock = data["clock"]
            reported = set(data["reported_packages"])
        except Exception:
            logger.exception("The saved morning routine file can't be read, so it starts fresh")
            return
        self._state, self._steps, self._on, self._clock, self._reported = state, steps, on, clock, reported

    def snapshot(self) -> dict[str, Any]:
        """What is saved to the Store."""
        return {
            "state": rules.state_to_dict(self._state),
            "steps": rules.steps_to_list(self._steps),
            "is_on": self._on,
            "clock": self._clock,
            "reported_packages": sorted(self._reported),
        }

    async def _async_save(self) -> None:
        await self._store.async_save(self.snapshot())

    async def _async_begin(self) -> None:
        sensor_id = self._entry.data[CONF_ALARM_SENSOR]
        tracker_id = self._entry.data[CONF_TRACKER]
        async with self._lock:
            if self._stopped:
                return
            self._unsubs.append(async_track_state_change_event(self._hass, [sensor_id], self._on_sensor))
            self._unsubs.append(async_track_state_change_event(self._hass, [tracker_id], self._on_tracker))
            self._unsubs.append(self._hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry))
            now = dt_util.utcnow()
            self._observe_sensor(self._hass.states.get(sensor_id), now)
            # A phone that left during downtime blocks the restart rule. One that came home doesn't
            # start anything: the stored location decides until the rule has run.
            tracker = self._hass.states.get(tracker_id)
            if tracker is not None and tracker.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "home"):
                self._state.last_location = tracker.state
            due = rules.steps_after_restart(self._state, self._allowed_steps(), self._on, now)
            await self._async_save()
            await self._async_run(due)
            self._observe_tracker(tracker)
            self._started = True
            await self._async_evaluate(dt_util.utcnow())

    async def _async_change(self, change: Callable[[datetime], None] | None = None) -> None:
        async with self._lock:
            if self._stopped:
                return
            now = dt_util.utcnow()
            if change is not None:
                change(now)
            if not self._started:
                # The restart rule has to decide first, so the first evaluation is in _async_begin.
                await self._async_save()
                self._notify()
                return
            await self._async_evaluate(now)

    async def _async_evaluate(self, now: datetime) -> None:
        try:
            # Asking records the steps that can no longer run, so it comes before saving.
            due = rules.steps_to_run(self._state, self._allowed_steps(), self._on, now)
            await self._async_save()
            await self._async_run(due)
        finally:
            self._schedule(dt_util.utcnow())
            self._notify()

    def _allowed_steps(self) -> list[Step]:
        return [step for step in self._steps if item_is_allowed(self._hass, step.item)]

    async def _async_run(self, due: list[tuple[Alarm, Step]]) -> None:
        for alarm, step in due:
            if self._stopped:
                return
            # Saved before the call: a crash can lose a run but never repeat one.
            alarm.ran.add(step.item)
            await self._async_save()
            # A stop during the save means a reload may have started a new routine that sees this
            # step as already run. Starting it here too could run it twice, so it is lost instead.
            if self._stopped:
                return
            # The call can take as long as the script or automation does, so it never holds the lock.
            self._hass.async_create_task(self._async_call_step(step), f"{DOMAIN} step {step.item}")

    async def _async_call_step(self, step: Step) -> None:
        domain, service = STEP_SERVICES[step.item.split(".", 1)[0]]
        error = None
        try:
            await self._hass.services.async_call(domain, service, {"entity_id": step.item}, blocking=True)
        except Exception as err:
            error = str(err) or type(err).__name__
            logger.error("Step %s failed: %s", step.item, error, exc_info=True)
        result = "failed" if error else "started"
        self._last_result = {
            "item": step.item,
            "step": step.offset_minutes,
            "result": result,
            "error": error,
            "time": dt_util.utcnow().isoformat(),
        }
        self._hass.bus.async_fire(
            EVENT_STEP_RAN,
            {
                "routine": self._entry.entry_id,
                "step": step.offset_minutes,
                "item": step.item,
                "result": result,
            },
        )
        self._notify()

    def _schedule(self, now: datetime) -> None:
        self._cancel_timer()
        if self._stopped:
            return
        when = rules.next_wakeup(self._state, self._steps, now)
        if when is not None:
            self._timer = async_track_point_in_utc_time(self._hass, self._on_timer, when)

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer()
            self._timer = None

    def _cancel_no_alarm_timer(self) -> None:
        if self._no_alarm_timer is not None:
            self._no_alarm_timer()
            self._no_alarm_timer = None

    @callback
    def _on_timer(self, _now: datetime) -> None:
        self._timer = None
        self._hass.async_create_task(self._async_change())

    @callback
    def _on_no_alarm_timer(self, _now: datetime) -> None:
        self._no_alarm_timer = None
        self._hass.async_create_task(self._async_change(lambda now: rules.observe_no_alarm(self._state, now)))

    @callback
    def _on_sensor(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        self._hass.async_create_task(self._async_change(lambda now: self._observe_sensor(new_state, now)))

    @callback
    def _on_tracker(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        self._hass.async_create_task(self._async_change(lambda _now: self._observe_tracker(new_state)))

    @callback
    def _on_registry(self, event: Event) -> None:
        if event.data.get("entity_id") in {step.item for step in self._steps}:
            self._hass.async_create_task(self._async_change())

    def _observe_current_sensor(self, now: datetime) -> None:
        self._observe_sensor(self._hass.states.get(self._entry.data[CONF_ALARM_SENSOR]), now)

    def _observe_sensor(self, new_state: State | None, now: datetime) -> None:
        if new_state is None or new_state.state == STATE_UNKNOWN:
            return
        if new_state.state == STATE_UNAVAILABLE:
            if self._no_alarm_timer is None:
                self._no_alarm_timer = async_track_point_in_utc_time(
                    self._hass, self._on_no_alarm_timer, now + rules.NO_ALARM_AFTER
                )
            return
        time = dt_util.parse_datetime(new_state.state)
        if time is None:
            logger.warning("The next alarm sensor reported a value that isn't a time")
            return
        self._cancel_no_alarm_timer()
        package = new_state.attributes.get("Package") or None
        if package is not None:
            self._reported.add(package)
        rules.observe_entry(
            self._state, dt_util.as_utc(time), package, self._clock, self._require_zero_seconds, now
        )

    def _observe_tracker(self, new_state: State | None) -> None:
        if new_state is not None and new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._state.last_location = new_state.state
