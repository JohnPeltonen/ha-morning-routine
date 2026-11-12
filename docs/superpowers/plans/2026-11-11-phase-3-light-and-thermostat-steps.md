# Phase 3: Lights and Thermostats as Steps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A step can turn a light on or off, turn a one-temperature thermostat on or off, or set "heat to" and "cool to" on a thermostat that takes a range, chosen straight from the card with no label.

**Architecture:** A step gains an id, an action and up to four settings. The alarm rules track what ran by the step's key (its id, or its item when it has no id), so a device can be a step more than once. A new server module works out what type a device is and which Home Assistant actions a step sends. The view tells the card what each item can do, and the card's form changes with the item chosen.

**Tech Stack:** Python 3.13, Home Assistant 2026.10+, probatio, pytest, one plain JavaScript file, Node's built-in test runner.

**Spec:** `docs/superpowers/specs/2026-11-01-morning-routine-integration-design.md`, section "What a step can run" (rewritten 2026-11-11) and "The card".

**Budget:** 1 session / about 400k tokens

**Execution:** inline in one session, then one fresh reviewer on the whole change. The owner chose this on 2026-11-11 and is away while it runs.

## Global Constraints

- Scripts, scenes and automations still need the "morning routine" label and can still be a step once per routine. None of that changes.
- Lights (`light`) and thermostats (`climate`) need no label. No other device type is offered.
- Every check runs on the server. A refused change changes nothing.
- A step saved by version 0.2.0 must load and behave the same. What already ran for an alarm must still count as ran.
- Card text is plain words. No red. No clock times. The card builds its page with the `h()` helper and never with `innerHTML`.
- `rules.py` never imports `homeassistant`.
- Nothing about the owner's house goes in code, tests, docs or commit messages. Tests use made-up names.
- Say "type", never "kind".

## Review Focus

1. **A step saved by 0.2.0** (no id, no action) loads, shows in the card, and is not run a second time for an alarm it already ran for.
2. **Two steps for one device** each run once, and editing one doesn't change or re-run the other.
3. **A device that is unavailable or deleted** when another step is edited: the unchanged step is kept, not refused.
4. **A range thermostat that is in heat mode, cool mode or off** when its step runs: only the fitting number is sent, or the step fails with a reason. Nothing is turned on.
5. **A setting outside what the device takes** (brightness on a light that doesn't dim, a temperature above the device's highest, heat above cool) is refused on the server even if the card is bypassed.

---

### Task 1: Steps carry an id, an action and settings

**Files:** Modify `custom_components/morning_routine/rules.py`. Test `tests/rules/test_steps.py`, `tests/rules/test_storage.py`.

**Interfaces, produces:**

```python
@dataclass(frozen=True)
class Step:
    item: str
    offset_minutes: int
    enabled: bool = True
    id: str = ""
    action: str = "run"            # run, turn_on, turn_off, set_temperature
    brightness: int | None = None
    temperature: float | None = None
    heat_to: float | None = None
    cool_to: float | None = None

    @property
    def key(self) -> str           # id, or item when id is empty
```

- `steps_to_run`, `steps_after_restart` record `step.key` in `alarm.ran` and `alarm.dropped`.
- `steps_to_list` writes `id`, `action` and each setting only when it differs from the default, so a 0.2.0 step is written exactly as before. `steps_from_list` reads them with defaults.

- [ ] Tests first: two steps with the same item and different ids both come due and each is recorded under its own key; a step with no id is recorded under its item; a list round-trips with every new field; a 0.2.0 list loads to steps with action `run`; an old-shape step serialises to the three old keys only.
- [ ] Run, see them fail. Implement. Run `.venv/Scripts/python.exe -m pytest -q`. Commit.

### Task 2: Device types and the actions a step sends

**Files:** Create `custom_components/morning_routine/devices.py`. Modify `const.py` (`DEVICE_DOMAINS = ("light", "climate")`). Test `tests/ha/test_devices.py`.

**Interfaces, produces:**

```python
def device_info(hass, entity_id: str) -> dict | None
# None when the domain isn't offered, there is no state, or the state is unavailable.
# {"type": "light", "actions": ["turn_on", "turn_off"], "brightness": bool}
# {"type": "thermostat", "actions": [...], "temperature": bool, "min_temp": float | None, "max_temp": float | None}
# {"type": "thermostat_range", "actions": ["set_temperature"], "min_temp": ..., "max_temp": ...}

def device_calls(hass, step: Step) -> list[tuple[str, str, dict]]
# Raises HomeAssistantError when a range thermostat is off, missing, or in a mode that takes no temperature.
```

- A light dims when `supported_color_modes` holds anything other than `onoff`.
- A `climate` entity is `thermostat_range` when its supported features include the target temperature range (2). Otherwise it is `thermostat`, with `turn_on` when it supports turning on (256), `turn_off` when it supports turning off (128), and `temperature` when it supports a target temperature (1). A `thermostat` with neither action is not offered.
- `turn_on` with a temperature sends `climate.turn_on`, then `climate.set_temperature`.
- `set_temperature` sends `target_temp_low` and `target_temp_high` in `heat_cool` mode or when the state shows both numbers; `temperature: cool_to` in `cool`; `temperature: heat_to` in `heat` and `auto`.

- [ ] Tests first for every row above, then implement, run the WSL suite, commit.

### Task 3: Check device steps that come from a person

**Files:** Modify `step_input.py`, `__init__.py`, `websocket.py`, `strings.json`, `translations/en.json`. Test `tests/ha/test_service.py`, `tests/ha/test_websocket.py`.

**Interfaces:** `parse_steps(hass, raw, existing: Sequence[Step] = ()) -> list[Step]` replaces the `keep` argument. Both callers pass `routine.steps`.

- A step may also carry `id`, `action`, `brightness`, `temperature`, `heat_to`, `cool_to`.
- Script, scene, automation: as before. Any action other than `run`, or any setting, is `invalid_step`. Their id is always empty, so their key stays their item.
- Light or thermostat: the action must be one the device offers (`action_not_offered`); brightness is a whole number from 1 to 100 on a light that dims (`brightness_out_of_range`); temperatures are numbers inside the device's range (`temperature_out_of_range`); heat must be below cool (`heat_not_below_cool`); a setting the action doesn't take is `invalid_step`.
- A device step with no id gets the id of an existing step with the same item and action that this list hasn't used yet, or a new random one. Ids must be unique in the list.
- A step that is unchanged from an existing one (same key, item, action and settings) skips the device checks, so a device that is unavailable or gone doesn't block other edits.
- Any other domain is `item_not_allowed`. Its message now names lights and thermostats too.

- [ ] Tests first (each refusal changes nothing; non-admin adds a light step over WebSocket; two steps for one light are kept with different ids; ids are stable when the list is sent again without them; an unchanged step for a deleted device is kept). Implement, run both suites, commit.

### Task 4: Run device steps

**Files:** Modify `routine.py`. Test `tests/ha/test_routine.py`, `tests/ha/conftest.py` (record light and climate calls).

- `step_is_allowed(hass, step) -> bool` in `routine.py`: a `run` step as today; a device step when the device has a state.
- `_allowed_steps` uses it. `alarm.ran` gets `step.key`.
- `_async_call_step` sends each call from `device_calls` in order and stops at the first failure. The event and `last_result` gain `action`.

- [ ] Tests first: a light step runs at its time and sends brightness; on and off steps for one light both run; a thermostat turn-on sends two calls in order; a range step in heat mode sends one number; a range step on an off thermostat is recorded as failed and sends nothing; a step whose device has no state doesn't run; a 0.2.0 store with a step already in `ran` doesn't run it again. Implement, run, commit.

### Task 5: The view tells the card what each item can do

**Files:** Modify `view.py`. Test `tests/ha/test_view.py`, `tests/ha/test_websocket.py`.

- Each step gains `id` (its key), `action`, `type` (`run`, a device type, or `None` when unknown), and the four settings (`None` when unset). `available` uses `step_is_allowed`.
- `items` lists labelled items with `"type": "run"`, then every light and thermostat that `device_info` describes and that isn't hidden in the entity registry, each with its `device_info` fields. One list, sorted by name.
- The view gains `temperature_unit`.
- `no_label` is no longer a problem, because a routine can be built without the label.

- [ ] Tests first, implement, run, commit.

### Task 6: Card logic

**Files:** Modify `www/morning-routine-card.js` (top half). Test `tests/card/card-logic.test.mjs`.

**Produces (exports):** `stepDetail(step, unit)`, `itemGroups(items)`, `searchItems(items, text, keepItem)`, `actionChoices(entry)`, `settingsError(entry, action, fields)`, `settingsOf(entry, action, fields)`; `formItems(view, editingId)`, `withToggled(view, id, enabled)`, `withSaved(view, editingId, step)`, `withRemoved(view, id)` now work by step id; steps sent to the server carry `id`, `action` and the settings that are set.

Exact text:

- Details: "Turn on", "Turn on at 40%", "Turn on at 115°F", "Turn off", "Heat to 68°F, cool to 74°F".
- Groups: "Lights", "Thermostats", "Scripts, scenes and automations".
- Actions: "Turn on", "Turn off", "Set temperatures".
- "Enter a brightness from 1 to 100, or leave it empty."
- "Enter a temperature from {low} to {high}, or leave it empty."
- "Enter a temperature from {low} to {high} in both boxes."
- '"Heat to" must be lower than "Cool to".'

- [ ] Tests first, implement, run `node --test "tests/card/*.test.mjs"`, commit.

### Task 7: The form and the step rows

**Files:** Modify `www/morning-routine-card.js` (element), `tests/card/demo.html`, `tests/card/card-element.test.mjs` only if it breaks.

- The form's picker is a search box above a grouped native `<select>`. A new form starts on "Choose one".
- Below it, the action and settings for the chosen item, rebuilt only when the item or action changes so typed values survive a new view.
- A step row shows its detail under its name. A device step that is gone says "No longer available. It was deleted."
- The form notes that scripts, scenes and automations appear once an admin adds the label.
- The demo's fake server gets lights and thermostats and keeps ids.

- [ ] Build, run all suites, run the demo in a browser at 360 pixels: add a light with brightness, add the same light again turning off, add a range thermostat, edit and remove, each refusal. Commit.

### Task 8: Documents, version, final review

- [ ] Version 0.3.0 in `manifest.json`. README: what a step can be, the form, `set_steps` fields. `docs/status.md`: where Phase 3 stands.
- [ ] One fresh reviewer on the whole change with this plan, the spec and the Review Focus. Fix Critical and Important findings with a failing test first. Record the rest in `docs/status.md`.
- [ ] Push. The owner's server is not touched.

## Later phases

### Motion steps
Run a step on the next motion after a set time. Waits for a sensor that works while people are home.

### More device types
Switches, fans and speakers, if the owner wants them after using lights and thermostats.

### Release
Check the card on a real phone and publish.
