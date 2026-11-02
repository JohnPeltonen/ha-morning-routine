# Morning Routine, Phase 1: Rules, Settings and First Install. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Budget:** 1 session / ~500k tokens

**Goal:** One phone's routine runs its time steps around real alarms on the owner's server, turned on and off from ordinary entities, with steps set by an admin service.

**Architecture:** All alarm decisions live in `rules.py`, which has no `homeassistant` imports and is tested locally. `routine.py` connects those rules to Home Assistant: it listens for sensor and tracker changes, sets the next timer, saves state, and runs items. Every change leads to the same question, "what should run now?", so on-time steps, late alarms and cleared blocks all follow one code path.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.0 or newer, `probatio`, `pytest`, `pytest-homeassistant-custom-component==0.13.371`.

**Spec:** `docs/superpowers/specs/2026-11-01-morning-routine-integration-design.md`. Read it before starting a task.

## Global Constraints

- Domain `morning_routine`. Home Assistant 2026.10.0 or newer. Forms use `probatio`, not `voluptuous`.
- Follow the tooling of the owner's `ha-amerec-steam` repo, copied below where it matters.
- Public repo: no household names, addresses, entity IDs from the owner's house, or real phone identifiers in code, docs or test data. Test data uses made-up values such as `sensor.test_phone_next_alarm`.
- snake_case, absolute imports (`from custom_components.morning_routine.const import DOMAIN`), `logger = logging.getLogger(__name__)` with %-style formatting, `T | None`, minimal docstrings. Use `type`, never `kind`.
- `rules.py` must never import `homeassistant`.
- Commit straight to `main` with explicit paths. Never push: the owner pushes.
- Native Windows can't run Home Assistant. `pytest` locally runs the rules and translation tests only. `tests/ha` runs in GitHub Actions, which needs a push, so **tests/ha results are only known after the owner pushes.** Task 9 covers this.

## Decisions This Plan Adds to the Spec

- **A restart drops overdue steps that aren't under 5 minutes late, including blocked ones.** The spec's downtime rule only covers steps missed during downtime, but the integration has no record of when it stopped. Dropping is the direction that can't start anything.
- **A step at or after the alarm runs on time or not at all.** "On time" means within 10 seconds of its time, so a timer that fires slightly late still counts.
- **An alarm that was pushed behind an earlier alarm sleeps.** It runs nothing until it becomes current again, and its record is removed 90 minutes after its time.
- **Snoozes chain.** The 20-minute gap is measured from the latest time seen for that alarm, so 9:03, 9:08, 9:13, 9:18, 9:23 is one alarm. Once an alarm has gone off, its steps keep their original times.
- **Changing the clock** clears the current alarm, then reads the sensor again with the new clock.
- **Two steps in one routine can't use the same item,** because steps are matched by item.

## Left for Phase 2

The card, WebSocket commands, motion steps, plain-word problem messages, reading past apps from sensor history for the clock list, and refusing scripts that need input fields.

## Review Focus

Each line has a test in the task named.

1. A brief `unavailable` or `unknown` on the tracker at the moment a step is due: the step still runs, using the last real location. (Task 5)
2. Home Assistant restarts while steps have already run for the current alarm: nothing runs a second time. (Task 5)
3. The phone's connection drops for over 60 seconds and comes back with the same alarm: steps that ran don't run again, and steps still ahead stay scheduled. (Task 2, Task 5)
4. The sensor still shows yesterday's time, as it does with the phone's Allow list on: nothing runs. (Task 2)
5. A labeled item loses its label or is deleted after being added: the step doesn't run, nothing else breaks, and it can still run if the label comes back. (Task 5)

---

## File Structure

```
custom_components/morning_routine/
  __init__.py        setup, unload, removal, forwards platforms, registers the service
  manifest.json
  const.py           domain, config keys, label name, event name
  rules.py           entry filter, alarm tracking, what runs now, save format. No homeassistant
  clocks.py          the clock list. No homeassistant
  routine.py         Routine class: connects rules to Home Assistant
  config_flow.py     choose a phone; options for the :00 setting
  entity.py          base entity
  switch.py          routine on/off, skip next alarm
  select.py          clock to watch
  sensor.py          current alarm, last ignored entry
  diagnostics.py     last step result and failure
  services.yaml      temporary set_steps service
  strings.json
  translations/en.json
tests/
  conftest.py        leaves out tests/ha when Home Assistant isn't installed
  rules/conftest.py  loads rules.py and clocks.py on their own
  rules/test_entries.py, test_alarms.py, test_steps.py, test_phone_replays.py, test_storage.py, test_clocks.py
  test_translations.py
  ha/conftest.py, test_config_flow.py, test_routine.py, test_entities.py, test_service.py
```

---

### Task 1: Repo tooling and the integration's skeleton

**Files:**
- Create: `hacs.json`, `pyproject.toml`, `requirements_test.txt`, `requirements_test_ha.txt`, `.gitignore`, `.github/workflows/hassfest.yaml`, `.github/workflows/tests.yaml`
- Create: `custom_components/morning_routine/manifest.json`, `const.py`, `strings.json`, `translations/en.json`
- Test: `tests/conftest.py`, `tests/test_translations.py`, `tests/rules/conftest.py`

**Interfaces:**
- Produces: `const.py` with `DOMAIN = "morning_routine"`, `CONF_ALARM_SENSOR = "alarm_sensor"`, `CONF_TRACKER = "tracker"`, `CONF_DEVICE_ID = "device_id"`, `CONF_REQUIRE_ZERO_SECONDS = "require_zero_seconds"`, `LABEL_NAME = "morning routine"`, `EVENT_STEP_RAN = "morning_routine_step_ran"`, `SERVICE_SET_STEPS = "set_steps"`, `ALLOWED_DOMAINS = ("script", "scene", "automation")`.

- [ ] **Step 1: Copy the tooling files from `ha-amerec-steam`**

Copy `pyproject.toml`, `requirements_test.txt`, `requirements_test_ha.txt`, `.gitignore`, `.github/workflows/hassfest.yaml` and `tests/conftest.py` unchanged. Copy `tests.yaml`, renaming the first job's `panel` and `Panel tests` to `rules` and `Rules tests`. Copy `tests/test_translations.py`, changing the folder to `morning_routine`.

`hacs.json`: `{"name": "Morning Routine", "homeassistant": "2026.10.0"}`.

`tests/rules/conftest.py` inserts `custom_components/morning_routine` into `sys.path`, so `import rules` and `import clocks` work without running the package's `__init__.py`. The steam repo's `tests/panel/conftest.py` shows the pattern.

- [ ] **Step 2: Write the manifest and the first strings**

```json
{
  "domain": "morning_routine",
  "name": "Morning Routine",
  "after_dependencies": ["automation", "mobile_app", "person", "scene", "script"],
  "codeowners": ["@JohnPeltonen"],
  "config_flow": true,
  "documentation": "https://github.com/JohnPeltonen/ha-morning-routine",
  "integration_type": "service",
  "iot_class": "calculated",
  "issue_tracker": "https://github.com/JohnPeltonen/ha-morning-routine/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

Start `strings.json` as `{}` with an identical `translations/en.json`. Later tasks add to both.

- [ ] **Step 3: Run the tests**

Run: `pytest -v`
Expected: `test_translations_match_strings` PASSES.

- [ ] **Step 4: Commit**

Commit all of the above with explicit paths: "Add repo tooling and integration skeleton".

---

### Task 2: Which entries count, and tracking the current alarm

**Files:**
- Create: `custom_components/morning_routine/rules.py`
- Test: `tests/rules/test_entries.py`, `tests/rules/test_alarms.py`

**Interfaces:**
- Produces, in `rules.py`:
  - Constants: `SAME_ALARM_GAP = timedelta(minutes=20)`, `NO_ALARM_AFTER = timedelta(seconds=60)`, `CLOCK_SKEW = timedelta(seconds=5)`, `RECORD_KEPT = timedelta(minutes=90)`.
  - `class IgnoreReason(StrEnum)`: `NO_CLOCK`, `WRONG_APP`, `NOT_ON_THE_MINUTE`, `IN_THE_PAST`.
  - `@dataclass Alarm`: `time: datetime`, `latest: datetime`, `went_off: bool = False`, `cancelled: bool = False`, `skipped: bool = False`, `ran: set[str]`, `dropped: set[str]`.
  - `@dataclass IgnoredEntry`: `time: datetime`, `package: str | None`, `reason: IgnoreReason`.
  - `@dataclass RoutineState`: `alarms: list[Alarm]`, `current: Alarm | None = None`, `skip_next: bool = False`, `last_location: str | None = None`, `last_ignored: IgnoredEntry | None = None`.
  - `check_entry(time: datetime, package: str | None, clock: str | None, require_zero_seconds: bool, now: datetime) -> IgnoreReason | None`
  - `settle(state: RoutineState, now: datetime) -> None`: marks the current alarm as gone off when `now >= time - CLOCK_SKEW`. If `skip_next` is on at that moment, sets `alarm.skipped = True` and `skip_next = False`. Removes alarms more than `RECORD_KEPT` past `time`, and clears `current` if it was removed.
  - `observe_entry(state: RoutineState, time: datetime, package: str | None, clock: str | None, require_zero_seconds: bool, now: datetime) -> None`
  - `observe_no_alarm(state: RoutineState, now: datetime) -> None`: called by `routine.py` after `unavailable` has lasted `NO_ALARM_AFTER`.
  - `change_clock(state: RoutineState) -> None`: sets `current = None`, keeping the records.

`observe_entry` and `observe_no_alarm` call `settle` first. All datetimes are timezone-aware.

- [ ] **Step 1: Write the failing tests for `check_entry`**

In `tests/rules/test_entries.py`, with `CLOCK = "com.sec.android.app.clockpackage"`:

```python
def test_real_alarm_counts(): assert check_entry(at("09:03:00"), CLOCK, CLOCK, True, NOW) is None
def test_no_clock_chosen(): assert check_entry(at("09:03:00"), CLOCK, None, True, NOW) is IgnoreReason.NO_CLOCK
def test_other_app(): assert check_entry(at("07:30:00"), ROUTINES, CLOCK, True, NOW) is IgnoreReason.WRONG_APP
def test_seconds_not_zero(): assert check_entry(at("07:00:03"), CLOCK, CLOCK, True, NOW) is IgnoreReason.NOT_ON_THE_MINUTE
def test_seconds_check_can_be_off(): assert check_entry(at("07:00:03"), CLOCK, CLOCK, False, NOW) is None
def test_stale_value_is_ignored(): assert check_entry(NOW - timedelta(minutes=91), CLOCK, CLOCK, True, NOW) is IgnoreReason.IN_THE_PAST
```

`NOW` is 2026-11-02 00:00 UTC, and `at()` builds a time later that day. Add a test that a wrong-app entry is reported as `WRONG_APP` even when its seconds aren't zero, so the order of the checks is fixed.

- [ ] **Step 2: Write the failing tests for alarm tracking**

In `tests/rules/test_alarms.py`, one test per row of the spec's table, in the same order. Each one starts from a state with a current alarm at 09:00, unless its name says otherwise.

```python
def test_same_time_is_a_repeat(): ...                  # same Alarm object, ran kept
def test_within_20_minutes_is_same_alarm(): ...        # 09:15 before 09:00: ran kept, time moves to 09:15
def test_exactly_20_minutes_is_same_alarm(): ...
def test_more_than_20_minutes_is_a_new_alarm(): ...    # 09:21: new Alarm is current
def test_earlier_is_a_new_alarm(): ...                 # 08:00: new Alarm is current, 09:00 kept
def test_earlier_entry_that_doesnt_count_keeps_current(): ...  # hidden alarm
def test_later_entry_that_doesnt_count_cancels(): ...  # cancelled True, current None, ran kept
def test_no_alarm_cancels_before_alarm_time(): ...
def test_no_alarm_after_alarm_time_doesnt_cancel(): ...
def test_change_at_alarm_time_means_it_rang(): ...     # later non-counting entry at 09:00:00: went_off True, not cancelled
def test_change_within_5_seconds_before_means_it_rang(): ...   # at 08:59:56
def test_change_6_seconds_before_is_cancelled(): ...   # at 08:59:54
```

Then the rules from "How these rules fit together" and this plan's decisions:

```python
def test_snooze_after_ring_is_same_alarm_and_keeps_its_time(): ...  # went off at 09:03, 09:08 arrives: time 09:03, latest 09:08
def test_snoozes_chain_past_20_minutes(): ...   # 09:03, 09:08, 09:13, 09:18, 09:23, 09:28: one Alarm
def test_same_time_comes_back_after_cancel(): ...   # same Alarm object, cancelled False, ran kept
def test_new_alarm_keeps_gone_off_alarm_in_list(): ...
def test_alarm_behind_earlier_alarm_comes_back_with_its_record(): ...
def test_record_removed_90_minutes_after_alarm(): ...
def test_stale_entry_doesnt_become_current(): ...   # also records last_ignored with IN_THE_PAST
def test_ignored_entry_is_recorded_with_reason(): ...
def test_change_clock_clears_current_and_keeps_records(): ...
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/rules -v`
Expected: FAIL, because `rules` has no such names.

- [ ] **Step 4: Implement them in `rules.py`**

The order inside `observe_entry` after `settle`:

1. Call `check_entry`. If the entry doesn't count, record `last_ignored`, then: if there's a current alarm, it hasn't gone off, and the entry's time is after `current.time`, cancel it and clear `current`. Otherwise do nothing. A stale entry never cancels anything.
2. If it counts and equals `current.latest` or `current.time`: do nothing.
3. If it counts and is after `current.latest` by up to `SAME_ALARM_GAP`: set `latest`. Also set `time` if the alarm hasn't gone off.
4. Otherwise, look in `alarms` for one whose `time` or `latest` equals the entry. If found, set `cancelled = False` and make it current. If not, append a new `Alarm` and make it current. Then call `settle` again, so an alarm whose time has already passed is marked as gone off.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/rules -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

Commit `rules.py` and the two test files: "Add entry filter and alarm tracking".

---

### Task 3: What should run now

**Files:**
- Modify: `custom_components/morning_routine/rules.py`
- Test: `tests/rules/test_steps.py`, `tests/rules/test_phone_replays.py`

**Interfaces:**
- Consumes: everything in Task 2's Produces.
- Produces, in `rules.py`:
  - Constants: `ON_TIME_GRACE = timedelta(seconds=10)`, `LATE_LIMIT = timedelta(minutes=5)`.
  - `@dataclass(frozen=True) Step`: `item: str`, `offset_minutes: int`, `enabled: bool = True`.
  - `is_home(state: RoutineState) -> bool`: `state.last_location == "home"`.
  - `steps_to_run(state: RoutineState, steps: list[Step], routine_on: bool, now: datetime) -> list[tuple[Alarm, Step]]`
  - `steps_after_restart(state: RoutineState, steps: list[Step], routine_on: bool, now: datetime) -> list[tuple[Alarm, Step]]`: applies the 5-minute rule and adds everything else overdue to `alarm.dropped`.
  - `next_wakeup(state: RoutineState, steps: list[Step], now: datetime) -> datetime | None`: the soonest future step time, alarm time minus `CLOCK_SKEW`, or record removal.
  - `set_skip(state: RoutineState, on: bool, now: datetime) -> None`: calls `settle` first, so an alarm that has already gone off isn't skipped by mistake.

`steps_to_run` and `steps_after_restart` call `settle` first. `steps_to_run` doesn't change `ran`. `routine.py` records a step as run before starting it.

The decision inside `steps_to_run`, for each alarm:

```python
if alarm.skipped or not (alarm.went_off or (alarm is state.current and not alarm.cancelled)):
    continue
blocked = not routine_on or not is_home(state) or (state.skip_next and not alarm.went_off)
for step in steps:
    if not step.enabled or step.item in alarm.ran or step.item in alarm.dropped:
        continue
    run_at = alarm.time + timedelta(minutes=step.offset_minutes)
    if run_at > now or blocked:
        continue
    if now < alarm.time or now - run_at <= ON_TIME_GRACE:
        yield alarm, step
```

- [ ] **Step 1: Write the failing tests for time steps and catch-up**

In `tests/rules/test_steps.py`, with a 07:00 alarm and a step at -30 minutes unless the name says otherwise:

```python
def test_not_due_before_its_time(): ...                 # 06:29:59: nothing
def test_due_at_its_time(): ...                         # 06:30:00: runs
def test_after_ran_it_doesnt_run_again(): ...
def test_alarm_seen_late_runs_right_away(): ...         # alarm first observed 06:45
def test_alarm_seen_after_it_passed_runs_nothing(): ...
def test_at_alarm_step_runs_on_time(): ...              # offset 0, 07:00:00
def test_after_alarm_step_runs_on_time(): ...           # offset +10, 07:10:00
def test_after_alarm_step_blocked_at_its_time_is_lost(): ...  # home again 07:12: nothing
def test_grace_boundary(): ...                          # offset +10: 07:10:10 runs, 07:10:11 doesn't

# Blocked, then cleared: nothing at 06:30, runs at 06:45
def test_routine_turned_on_catches_up(): ...
def test_step_toggle_turned_on_catches_up(): ...
def test_skip_turned_off_catches_up(): ...
def test_phone_coming_home_catches_up(): ...
def test_step_added_with_passed_time_catches_up(): ...
def test_step_retimed_to_passed_time_catches_up(): ...
def test_clock_chosen_catches_up(): ...                 # observe_entry with the new clock at 06:45
def test_block_cleared_after_alarm_passed_runs_nothing(): ...   # 07:01

def test_retimed_step_that_ran_doesnt_run_again(): ...
def test_removed_and_readded_step_that_ran_doesnt_run_again(): ...
def test_retimed_to_later_runs_at_new_time(): ...
def test_edit_moves_steps_that_havent_run(): ...        # alarm 07:00 to 07:15: step at 06:45
def test_away_blocks_every_step(): ...
def test_named_zone_blocks(): ...                       # last_location "work"
def test_never_had_a_location_blocks(): ...             # last_location None
def test_gone_off_alarm_carries_on_after_new_alarm_is_current(): ...
def test_alarm_behind_an_earlier_alarm_runs_nothing(): ...
def test_cancelled_alarm_runs_nothing(): ...
```

- [ ] **Step 2: Write the failing tests for Skip next alarm and restarts**

```python
def test_skip_before_alarm_blocks_all_its_steps(): ...          # includes offset +10
def test_skip_used_up_when_alarm_goes_off(): ...                # skip_next False, alarm.skipped True
def test_skipped_alarm_stays_skipped_through_snooze(): ...
def test_skip_after_alarm_went_off_applies_to_next_alarm(): ... # +10 step of today's alarm still runs; tomorrow's blocked
def test_skip_with_no_alarm_known_waits_for_next(): ...
def test_skip_stays_on_when_alarm_is_cancelled(): ...
def test_skip_stays_on_when_alarm_is_replaced(): ...

def test_restart_runs_step_under_5_minutes_late(): ...          # 4:59 late: runs
def test_restart_drops_step_5_minutes_late(): ...               # 5:00 late: dropped, and no later catch-up
def test_restart_drops_overdue_blocked_step(): ...              # phone comes home later: nothing
def test_restart_leaves_future_steps_alone(): ...
def test_restart_doesnt_repeat_steps_that_ran(): ...
def test_next_wakeup_is_soonest_future_time(): ...
def test_next_wakeup_includes_alarm_time_for_skip(): ...
```

- [ ] **Step 3: Write the failing replay tests**

In `tests/rules/test_phone_replays.py`, replay the spec's two entry tables through `observe_entry` and `steps_to_run`, with a -30 minute step. Use made-up phone names.

```python
def test_first_phone_runs_once_for_the_0900_alarm(): ...   # clock com.google.android.deskclock
def test_first_phone_hidden_alarm_runs_when_it_appears(): ...  # appears 07:30:05, step due 08:30
def test_second_phone_moved_alarm_uses_new_time(): ...     # 06:42 moved to 09:03: new alarm
def test_second_phone_probable_snooze_runs_nothing_again(): ...  # 09:08 for 11 seconds after 09:03
def test_short_blip_keeps_the_alarm(): ...                 # unknown is ignored, no observe_no_alarm
def test_no_samsung_clock_false_entry_runs(): ...          # 07:00:03 and 22:30:03 on com.sec.android.app.clockpackage
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `pytest tests/rules -v`
Expected: the new tests FAIL.

- [ ] **Step 5: Implement them in `rules.py`**

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/rules -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

Commit `rules.py` and the two test files: "Decide which steps run now".

---

### Task 4: Saving state, and the clock list

**Files:**
- Modify: `custom_components/morning_routine/rules.py`
- Create: `custom_components/morning_routine/clocks.py`
- Test: `tests/rules/test_storage.py`, `tests/rules/test_clocks.py`

**Interfaces:**
- Produces:
  - `rules.state_to_dict(state: RoutineState) -> dict` and `rules.state_from_dict(data: dict) -> RoutineState`. Times are ISO strings, sets are sorted lists, and `current` is stored as its index in `alarms`.
  - `rules.steps_to_list(steps: list[Step]) -> list[dict]` and `rules.steps_from_list(data: list[dict]) -> list[Step]`.
  - `clocks.GOOGLE_CLOCK = "com.google.android.deskclock"`, `clocks.SAMSUNG_CLOCK = "com.sec.android.app.clockpackage"`, `clocks.NOT_CLOCKS = {"com.samsung.android.app.routines"}`.
  - `clocks.clock_options(manufacturer: str | None, reported: set[str], chosen: str | None) -> dict[str, str]`: package to plain name.

- [ ] **Step 1: Write the failing tests**

```python
def test_state_survives_a_round_through_json(): ...   # json.dumps then state_from_dict: equal, and current is the same object as its alarms entry
def test_empty_state_round_trip(): ...

def test_google_clock_on_every_phone(): assert GOOGLE_CLOCK in clock_options("Pixel", set(), None)
def test_samsung_clock_on_a_samsung_phone(): assert SAMSUNG_CLOCK in clock_options("samsung", set(), None)
def test_samsung_clock_hidden_on_other_phones(): assert SAMSUNG_CLOCK not in clock_options("Pixel", set(), None)
def test_samsung_clock_shown_if_reported(): assert SAMSUNG_CLOCK in clock_options("Pixel", {SAMSUNG_CLOCK}, None)
def test_routines_app_is_never_offered(): assert ROUTINES not in clock_options("samsung", {ROUTINES}, None)
def test_unknown_app_shows_its_package(): assert clock_options(None, {"com.example.clock"}, None)["com.example.clock"] == "com.example.clock"
def test_chosen_clock_always_offered(): ...           # even if nothing else would offer it
```

The manufacturer check ignores case, because the server reports `samsung` in lower case.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/rules -v`
Expected: the new tests FAIL.

- [ ] **Step 3: Implement them**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

Commit the three changed files and both test files: "Add state saving and the clock list".

---

### Task 5: The Routine class

**Files:**
- Create: `custom_components/morning_routine/routine.py`
- Test: `tests/ha/conftest.py`, `tests/ha/test_routine.py`

**Interfaces:**
- Consumes: `rules.py`, `clocks.py`, `const.py`.
- Produces: `class Routine`:
  - `__init__(self, hass: HomeAssistant, entry: ConfigEntry)`
  - `async def async_start(self) -> None`: loads the `Store`, reads the sensor and tracker, and runs the restart rule. If Home Assistant is still starting, it waits for `EVENT_HOMEASSISTANT_STARTED`, then does the same.
  - `def async_stop(self) -> None`: cancels listeners and timers.
  - `async def async_set_on(self, on: bool) -> None`
  - `async def async_set_skip(self, on: bool) -> None`
  - `async def async_set_clock(self, package: str) -> None`
  - `async def async_set_steps(self, steps: list[Step]) -> None`
  - Properties: `is_on: bool`, `skip_next: bool`, `clock: str | None`, `clock_options: dict[str, str]`, `current_alarm: datetime | None`, `last_ignored: IgnoredEntry | None`, `steps: list[Step]`, `last_result: dict | None`.
  - `def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]`
  - `def item_is_allowed(hass: HomeAssistant, item: str) -> bool` at module level: its domain is in `ALLOWED_DOMAINS`, and its entity registry entry has the label named `LABEL_NAME`.

Behavior:

- **Sensor changes:** a timestamp calls `observe_entry`, with `Package` from the attributes. `unknown` does nothing. `unavailable` starts a 60-second timer that calls `observe_no_alarm`, and any real value cancels it. Each new package seen is added to `reported_packages`.
- **Tracker changes:** any state other than `unavailable` or `unknown` updates `last_location`.
- **After every change:** save, ask `steps_to_run`, run the results, set one timer from `next_wakeup`, and notify listeners. Steps whose item fails `item_is_allowed` are left out of the list given to the rules.
- **Running a step:** add the item to `alarm.ran`, **await the `Store` save**, and only then call the service. A crash can lose a run but can't repeat one.
  - Script: `script.turn_on` with `blocking=True`. It returns when the script has started, without waiting for it to finish.
  - Scene: `scene.turn_on`. Automation: `automation.trigger`.
  - On `HomeAssistantError` or `ServiceNotFound`: log it, store it in `last_result`, and carry on with the next step.
  - Fire `EVENT_STEP_RAN` with `routine`, `step` (offset in minutes), `item` and `result` (`"started"` or `"failed"`).
- **Store** key is `morning_routine.<entry_id>`, holding `state`, `steps`, `is_on`, `clock` and `reported_packages`. The routine starts off, with no clock.

- [ ] **Step 1: Write `tests/ha/conftest.py`**

Add the `auto_enable_custom_integrations` fixture from the steam repo. Add a `phone` fixture that registers a `mobile_app` device with made-up names, a `sensor.test_phone_next_alarm` and a `device_tracker.test_phone`, and sets them to a timestamp and `home`. Add a `labeled_script` fixture that registers `script.test_step`, creates the label, and applies it. Add a `service_calls` fixture using `async_mock_service`.

- [ ] **Step 2: Write the failing tests**

In `tests/ha/test_routine.py`, using `async_fire_time_changed` and `freezegun`:

```python
async def test_step_runs_at_its_time_through_script_turn_on(hass, ...): ...
async def test_event_is_fired_with_result(hass, ...): ...
async def test_scene_and_automation_use_their_own_services(hass, ...): ...
async def test_ran_is_saved_before_the_service_is_called(hass, ...): ...
async def test_failed_step_is_recorded_and_next_step_still_runs(hass, ...): ...

# Review Focus 1
async def test_tracker_blip_at_step_time_uses_last_real_location(hass, ...): ...
async def test_not_home_blocks_and_coming_home_catches_up(hass, ...): ...

# Review Focus 2
async def test_restart_doesnt_repeat_a_step_that_ran(hass, ...): ...     # unload, set up again with the same Store
async def test_reload_starts_nothing_by_itself(hass, ...): ...
async def test_last_location_survives_restart_while_tracker_unavailable(hass, ...): ...

# Review Focus 3
async def test_sensor_unavailable_60_seconds_cancels_then_same_time_returns(hass, ...): ...  # ran kept, later step still runs
async def test_sensor_unavailable_59_seconds_changes_nothing(hass, ...): ...

# Review Focus 5
async def test_item_without_label_doesnt_run(hass, ...): ...
async def test_deleted_item_doesnt_run_and_others_do(hass, ...): ...
async def test_item_runs_when_label_comes_back_before_alarm(hass, ...): ...

async def test_sensor_entity_missing_at_start_doesnt_fail_setup(hass, ...): ...
async def test_changing_the_clock_drops_old_clocks_alarm(hass, ...): ...
```

- [ ] **Step 3: Check the test files parse locally**

Run: `pytest -v`
Expected: rules tests PASS, and `tests/ha` is left out. These tests first run for real in GitHub Actions (see Task 9). Run `python -m py_compile tests/ha/test_routine.py` to catch syntax mistakes.

- [ ] **Step 4: Implement `routine.py`**

Keep decisions in `rules.py`. If a test here needs a new decision, add it to `rules.py` with a local test.

- [ ] **Step 5: Commit**

Commit `routine.py`, `tests/ha/conftest.py` and `tests/ha/test_routine.py`: "Connect the rules to Home Assistant".

---

### Task 6: Setup screens

**Files:**
- Create: `custom_components/morning_routine/config_flow.py`
- Modify: `strings.json`, `translations/en.json`
- Test: `tests/ha/test_config_flow.py`

**Interfaces:**
- Consumes: `const.py`.
- Produces: `MorningRoutineConfigFlow` and an options flow. Entry data: `CONF_ALARM_SENSOR`, `CONF_TRACKER`, `CONF_DEVICE_ID`. Entry options: `CONF_REQUIRE_ZERO_SECONDS`, default `True`. The unique ID is the device ID.

A phone is any device with a `mobile_app` `sensor` entity whose unique ID ends in `_next_alarm`. The tracker is that device's `device_tracker` entity. The title is `"<Person>'s morning routine"`, using the `person` whose `device_trackers` attribute includes the tracker, or the device's name if there isn't one.

Exact text for the phone step's description: "Choose the phone whose alarms this routine should follow. If a phone isn't listed, turn on its Next alarm sensor in the Home Assistant Android app, under Settings, Companion app, Manage sensors. Make sure that sensor's Allow list is off."

- [ ] **Step 1: Write the failing tests**

```python
async def test_lists_phones_with_the_sensor(hass, phone): ...
async def test_creates_entry_with_sensor_tracker_and_device(hass, phone): ...
async def test_title_uses_the_linked_person(hass, phone): ...
async def test_title_falls_back_to_device_name(hass, phone): ...
async def test_same_phone_twice_aborts(hass, phone): ...
async def test_phone_with_sensor_turned_off_isnt_chosen_and_gets_instructions(hass, phone): ...
async def test_phone_without_a_tracker_shows_an_error(hass, phone): ...
async def test_no_phones_aborts_with_instructions(hass): ...
async def test_options_turn_off_the_seconds_check(hass, loaded): ...
```

- [ ] **Step 2: Check the test file parses**

Run: `python -m py_compile tests/ha/test_config_flow.py`
Expected: no output.

- [ ] **Step 3: Implement the flow and its text**

Use `probatio` and a `SelectSelector` for the phone list. Keep `strings.json` and `translations/en.json` identical.

- [ ] **Step 4: Run the local tests**

Run: `pytest -v`
Expected: all PASS, including `test_translations_match_strings`.

- [ ] **Step 5: Commit**

Commit the flow, both text files and the test file: "Add setup screens".

---

### Task 7: Entities, the set_steps service, and setup

**Files:**
- Create: `custom_components/morning_routine/__init__.py`, `entity.py`, `switch.py`, `select.py`, `sensor.py`, `diagnostics.py`, `services.yaml`
- Modify: `strings.json`, `translations/en.json`
- Test: `tests/ha/test_entities.py`, `tests/ha/test_service.py`

**Interfaces:**
- Consumes: `Routine` from Task 5.
- Produces: `type RoutineConfigEntry = ConfigEntry[Routine]`. Service `morning_routine.set_steps`.

Entities, one device per routine, all with `_attr_has_entity_name = True` and `_attr_should_poll = False`:

| Platform | Key | Name | Notes |
|---|---|---|---|
| switch | `routine` | Routine | Off until turned on |
| switch | `skip_next_alarm` | Skip next alarm | Turns itself off when the skipped alarm goes off |
| select | `clock` | Clock to watch | Options are plain names. `current_option` is `None` until chosen |
| sensor | `current_alarm` | Current alarm | Timestamp, diagnostic |
| sensor | `last_ignored_entry` | Last ignored entry | Timestamp, diagnostic. Attributes `package`, `reason` |

`diagnostics.py` returns `Routine.last_result`, the saved state and the steps.

Service `set_steps`, **temporary and admin only**, registered with `async_register_admin_service`:

```yaml
set_steps:
  fields:
    config_entry_id: {required: true, selector: {config_entry: {integration: morning_routine}}}
    steps: {required: true, selector: {object: {}}}
```

`steps` is a list of `{item: str, offset_minutes: int, enabled: bool}`, with `enabled` defaulting to true. Offsets must be between -720 and 720. The call is refused with `ServiceValidationError` if an item fails `item_is_allowed`, or if two steps use the same item. A refused call changes nothing.

- [ ] **Step 1: Write the failing tests**

```python
# test_entities.py
async def test_entities_are_created_on_one_device(hass, loaded): ...
async def test_routine_starts_off_with_no_clock(hass, loaded): ...
async def test_routine_switch_changes_the_routine(hass, loaded): ...
async def test_skip_switch_turns_itself_off_when_alarm_goes_off(hass, loaded): ...
async def test_select_lists_samsung_clock_on_a_samsung_phone(hass, loaded): ...
async def test_select_saves_the_chosen_clock_as_a_package(hass, loaded): ...
async def test_current_alarm_sensor_follows_the_routine(hass, loaded): ...
async def test_last_ignored_sensor_has_package_and_reason(hass, loaded): ...
async def test_non_admin_can_use_the_switches(hass, loaded, hass_read_only_user): ...
async def test_diagnostics_include_the_last_result(hass, loaded, hass_client): ...
async def test_unload_cancels_timers_and_listeners(hass, loaded): ...
async def test_removing_the_entry_removes_its_store(hass, loaded): ...

# test_service.py
async def test_set_steps_saves_and_schedules(hass, loaded, labeled_script): ...
async def test_set_steps_refuses_unlabeled_item(hass, loaded): ...
async def test_set_steps_refuses_other_domains(hass, loaded): ...  # light.test
async def test_set_steps_refuses_duplicate_items(hass, loaded, labeled_script): ...
async def test_set_steps_refuses_offset_out_of_range(hass, loaded, labeled_script): ...
async def test_set_steps_refused_for_non_admin(hass, loaded, hass_read_only_user): ...
async def test_set_steps_with_passed_time_runs_right_away(hass, loaded, labeled_script): ...
```

- [ ] **Step 2: Check the test files parse**

Run: `python -m py_compile tests/ha/test_entities.py tests/ha/test_service.py`
Expected: no output.

- [ ] **Step 3: Implement them**

Register the service in `async_setup`, so it exists when no entry is loaded. Remove the store in `async_remove_entry`.

- [ ] **Step 4: Run the local tests**

Run: `pytest -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

Commit all of the above: "Add entities and the temporary set_steps service".

---

### Task 8: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write it for someone reading cold**

It must say all of the following:

- What it does, and that the card is coming, so this version is set up by an admin.
- Android only: iPhones don't have the next-alarm sensor.
- Install as a HACS custom repository. Turn on the phone's Next alarm sensor and leave its Allow list off.
- The evidence is one night from two Samsung Galaxy S25-series phones, and other phones may behave differently.
- A step only runs when the phone reports `home`. A zone drawn on the property, such as a yard, would block steps.
- Items need the "morning routine" label, which an admin creates.
- Turning something on can start a step right away if its time has passed and the alarm is still ahead.
- An alarm cancelled while hidden behind another entry can't be detected, so its steps may still run.
- How to set steps with `morning_routine.set_steps`, with one made-up example.
- Credit to Sunrise Alarm and Phone Alarm Sync, as in the spec.

- [ ] **Step 2: Check for household details**

Ask the owner for the household's names and phone identifiers, run `git grep -n -i` for each one from the repo root, and don't write them into this repo.
Expected: the only match is the owner's GitHub name in repo URLs and `codeowners`.

- [ ] **Step 3: Commit**

Commit `README.md`: "Add README".

---

### Task 9: Final review, CI, and first install

The steps that change the owner's server need the owner's approval each time. If the owner can't be reached, stop and report. Don't work around it.

**Files:** none in this repo unless a fix is needed.

- [ ] **Step 1: Run a final review of the whole phase**

Use the most capable available model. Give it the spec, this plan and the diff. Fix anything that breaks a spec guarantee. File anything else as a GitHub issue, after confirming with the owner.

- [ ] **Step 2: Hand over for the push**

Run: `pytest -v`, and show the full output.
Then ask the owner to push. Nothing else can run the Home Assistant tests.

- [ ] **Step 3: Read the GitHub Actions results**

Run: `gh run list --repo JohnPeltonen/ha-morning-routine --limit 5`, then `gh run view <id> --log-failed` for any failure.
Expected: Hassfest, Rules tests and Home Assistant tests all pass. Fix failures with new commits, and ask the owner to push again.

- [ ] **Step 4: Install on the owner's server**

Get the owner's approval. Follow the owner's house rules: check `ListAgents` and tell peers, confirm a backup in `backup/info`, then install through HACS as a custom repository and restart. Read back that the integration loaded with no errors in the log.

- [ ] **Step 5: Test with a harmless script**

Get the owner's approval. Create the "morning routine" label and a test script that only creates a notification, then label it. Set up the phone, choose its clock, set one step at -2 minutes against a real test alarm, and turn the routine on. Someone has to set that alarm on the phone in person.

Check all of these from Home Assistant history:
- The script ran once, at the right time.
- `morning_routine_step_ran` was recorded.
- An entry from the wrong app, or off :00 seconds, was ignored and recorded.
- With the alarm deleted and no other alarm set, the sensor's real behavior matches the spec's finding 8. **This has only been read from source code, so record what's seen.**

- [ ] **Step 6: Set up the real routine**

Get the owner's approval. Create the real script, which is the owner's and lives outside this repo, label it, and set the real step. Put the two switches where the phone's user can reach them, coordinating with any session working on the dashboard. Read back the settings, and report what wasn't tested.

---

## Later Phases

- **Phase 2, the card and motion steps:** the WebSocket commands, the card and its registration, motion steps, and plain-word problem messages. Replaces the temporary service.
- **Phase 3, release:** check the card on a real phone, update the README and publish.
