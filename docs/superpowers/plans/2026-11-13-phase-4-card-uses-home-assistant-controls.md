# Phase 4: The Card Uses Home Assistant's Own Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The add-a-step form and the card's switches and clock dropdown are drawn with Home Assistant's standard controls, and the server is the one place that knows what a light or thermostat step can do.

**Architecture:** `devices.py` describes each item as a list of actions, each with its settings in Home Assistant's selector format. The checks in `step_input.py` and the view both read that description. The card loads Home Assistant's controls once, keeps the form's state in a plain object changed only by small pure functions, and draws that state with `ha-selector` and friends. The card's face falls back to its own switch and dropdown when Home Assistant's controls aren't loaded.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.0 and later, probatio, pytest, one plain JavaScript file with no build step, Node 24's built-in test runner, WSL Ubuntu for the Home Assistant tests and for a throwaway Home Assistant.

**Spec:** `docs/superpowers/specs/2026-11-12-card-uses-home-assistant-controls-design.md`. The owner approved it on 2026-11-13. The main design is `docs/superpowers/specs/2026-11-01-morning-routine-integration-design.md`.

**Budget:** 1 session / about 700k tokens

**Execution:** the owner chose this on 2026-11-13: a second agent reviews this plan, the session that wrote it builds every task itself, and a third agent reviews the whole change. The owner is away for about an hour while it runs.

## Where things run

The owner answered the spec's open question on 2026-11-13: the owner tries the card on the owner's own server and dashboard. This plan adds two things, because this computer has WSL and the owner is away during the build:

- **Home Assistant tests** run in WSL, straight from the Windows folder: `wsl -d Ubuntu -- bash -c 'cd /mnt/d/code/ha-morning-routine && /root/mr/.venv/bin/python -m pytest tests/ha -q -p no:cacheprovider'`. Checked on 2026-11-13: 215 passed in 53 seconds. That environment has Home Assistant 2026.10.0 and frontend 20260930.2, the oldest supported version.
- **The builder's own checks in a browser** use a throwaway Home Assistant 2026.10.0 started from that same WSL environment, with made-up devices from the `demo` integration. Task 1 sets it up. It never touches the owner's server.
- **The owner's trial** on the owner's server happens after this plan, with the owner present. It needs a push, an update and a restart, and each needs the owner's go.

Nothing is pushed in this plan. The owner's server is not touched in this plan.

## Global Constraints

- The oldest supported version stays Home Assistant 2026.10.0 (`hacs.json`). Raising it needs the owner's go.
- Lights and thermostats keep exactly the actions and settings they have in version 0.3.0. No new device type.
- How steps are saved doesn't change. `set_steps` takes the same step fields: `id`, `item`, `offset_minutes`, `enabled`, `action`, and `brightness`, `temperature`, `heat_to`, `cool_to` at the top level. Steps saved by 0.2.0 and 0.3.0 load and behave as before.
- Every check stays on the server. No check is added or removed. Step size guides the slider only; the server accepts a value between steps.
- The routine switch must always work, even when Home Assistant's controls don't load.
- The form never saves something different from what it shows.
- The card stays one plain JavaScript file with no build step. It builds its page with `h()` and never with `innerHTML`.
- Card text is plain words. No red. No clock times. The timeline, step names and "+ Add a step" button stay as they are.
- Not used: Home Assistant's device controls (the round dial, the big brightness bar) and its action editor.
- The repo is public. Tests, docs, screenshots and commit messages use made-up names and nothing about the owner's house.
- Absolute imports. `rules.py` never imports `homeassistant`. Say "type", never "kind".
- Commit to `main` with explicit paths (`git commit <paths> -F -`). The repo has one staged change that isn't part of this work (two stray spaces in the spec). Leave it staged and never commit the spec file.

## Review Focus

1. **Home Assistant's controls never load** (an old phone browser, or a later release moves them). The card's face draws and every switch and the clock dropdown still work with the card's own controls. The form shows one sentence. Nothing throws.
2. **A new view arrives while the form is open** (a light stops reporting that it dims, a thermostat changes mode, the chosen item is deleted). Save sends only what is on screen, and the form says that something changed.
3. **A step saved by 0.3.0 is opened and saved without touching a control.** The server gets back exactly the same settings: 68.3 stays 68.3 on a thermostat whose step is 1, and a light step with no brightness stays without one.
4. **A person who isn't an admin** uses the form. The picker lists the items, the controls load, and Save works.
5. **A phone 360 pixels wide.** The picker's list opens above the card's dialog and can be scrolled and chosen from. Pressing Enter inside any control never saves the step.

Tests that pin these are in Tasks 1, 5, 6 and 7, each marked "Review Focus".

---

### Task 1: A throwaway Home Assistant, and proof that the controls load

This is the riskiest assumption, so it is proved before anything else is built.

**Files:**
- Create: `tests/try/configuration.yaml`, `tests/try/start.sh`, `tests/try/set_up.py`
- Modify: `CLAUDE.md` (Commands), `docs/status.md`

**Produces:**
- `tests/try/start.sh`: starts Home Assistant 2026.10.0 in WSL on port 8123 with its settings folder at `/root/mr-try` (outside the repo) and `custom_components/morning_routine` linked to this repo's folder. `configuration.yaml` is as small as will run the frontend, `demo`, `script`, `scene` and `automation`.
- `tests/try/set_up.py`: run once against a fresh instance. Afterwards there is an admin account `tester`, a normal account `member`, a made-up phone with a Next alarm sensor and a location entity (through Home Assistant's own `mobile_app` registration calls), a "morning routine" label on one made-up script, one routine, and a dashboard holding the card. The password is a fixed throwaway in the script, because the instance only listens on this computer.
- The loading recipe for Task 6: the exact calls that get Home Assistant's controls defined on 2026.10.0. Starting point: `await window.loadCardHelpers()`, create one of Home Assistant's own cards with the helpers, and `await` that card class's `getConfigElement()`.

- [ ] **Step 1:** Write the three files. Start the instance and run `set_up.py`. Check: the dashboard shows the 0.3.0 card for `tester` in a browser.
- [ ] **Step 2: Prove the controls, as `tester`.** With a scratch script run in the dashboard page (not committed), confirm each of these on 2026.10.0. Record a yes or no for each in `docs/status.md`.
  1. After the recipe, `customElements.get` returns a class for `ha-selector`, `ha-switch`, `ha-checkbox`, `ha-formfield` and `ha-button`.
  2. `ha-selector` draws each of: `{entity: {include_entities: [...]}}` (the entity picker, offering only those), `{button_toggle: {options: [{value, label}]}}`, `{number: {min, max, step, mode: "slider", unit_of_measurement}}` (a slider with a number box), `{number: {min: 0, max: 720, mode: "box"}}`, and `{select: {mode: "dropdown", options: [{value, label}]}}`.
  3. Each one fires `value-changed` with `event.detail.value` when a person changes it.
  4. A slider with `step: 1` given the value `68.3` does not fire `value-changed` by itself.
  5. Inside a `<dialog>` opened with `showModal()` in a card's shadow root, 360 pixels wide: the entity picker's list and the dropdown's list open above the dialog and an item can be chosen. (Review Focus 5)
  6. Setting `checked` on `ha-switch` from code moves it, and a tap fires `change`.
- [ ] **Step 3: Repeat checks 1, 2 and 5 as `member`.** (Review Focus 4)
- [ ] **Step 4: Rule on what was found.**
  - One selector missing or different: use the nearest standard control and record it (for example `select` in list mode for the toggle buttons).
  - `ha-button` or `ha-checkbox` missing: the card draws its own, styled to match. Record it.
  - The controls can't be loaded at all, or load for `tester` and not for `member`: **stop the build** and write the hand-off for the owner.
- [ ] **Step 5:** Fill in `CLAUDE.md` Commands (the WSL test command above, and how to start the throwaway). Commit.

### Task 2: The server describes each item's actions and settings

**Files:**
- Modify: `custom_components/morning_routine/devices.py`
- Test: `tests/ha/test_devices.py`

**Produces:**

```python
ACTION_NAMES = {"run": "Run", "turn_on": "Turn on", "turn_off": "Turn off", "set_temperature": "Set temperatures"}
SETTING_NAMES = {"brightness": "Brightness", "temperature": "Temperature", "heat_to": "Heat to", "cool_to": "Cool to"}
RUN_ACTIONS: list[dict]   # [{"action": "run", "name": "Run", "settings": []}]

def describe_device(hass: HomeAssistant, entity_id: str) -> list[dict[str, Any]] | None
# The actions a step can take on this light or thermostat. None when it can't be offered right now
# (same cases as device_info today). Each action: {"action", "name", "settings"}.
# Each setting: {"key", "name", "optional": bool, "start": number, "selector": {"number": {...}}}.

def step_detail(hass: HomeAssistant, step: Step) -> str
# "" for a run step. Otherwise the words the card shows under the step's name.
```

`describe_device` replaces `device_info`, which is removed in Task 4 once nothing calls it. Which actions and settings each device type has is unchanged from `device_info`.

Values the spec pins:
- Brightness: `{"number": {"min": 1, "max": 100, "step": 1, "mode": "slider", "unit_of_measurement": "%"}}`, optional. `start` is the light's current brightness as a percent (its `brightness` attribute is 0 to 255), kept within 1 to 100, or 100 when it reports none.
- Temperatures: `min` and `max` are the device's `min_temp` and `max_temp`. `step` is its `target_temp_step` when that is a number above 0, otherwise 1 in Fahrenheit and 0.5 in Celsius. `unit_of_measurement` is `hass.config.units.temperature_unit`. `mode` is `"slider"`.
- A thermostat that reports no limits gets Home Assistant's own defaults: 45 to 95 in Fahrenheit, 7 to 35 in Celsius. Ruling: a slider needs limits, and a real thermostat always reports them. Cost if wrong: a hand-made state with no limits is now held to these.
- One-temperature thermostat, `temperature`: optional. `start` is its current `temperature` attribute when that is a number within the limits, otherwise the middle of the range rounded to a step.
- Range thermostat, `heat_to` and `cool_to`: not optional. `start` is its `target_temp_low` and `target_temp_high` when both are numbers within the limits and low is below high. Otherwise one third and two thirds of the way up the range, each rounded to a step.
- Detail text, exactly as the card writes it today: "Turn on", "Turn on at 40%", "Turn on at 115°F", "Turn off", "Heat to 68°F, cool to 74°F". Numbers print with `f"{value:g}"`.

- [ ] **Step 1: Write the failing tests** in `tests/ha/test_devices.py`:
  - `test_a_light_that_dims_describes_turn_on_with_an_optional_brightness`: equals the spec's example for `light.lamp`, with `"start": 100`.
  - `test_brightness_starts_at_the_lights_current_brightness`: attribute `brightness: 102` gives `start == 40`; `brightness: 1` gives `start == 1`.
  - `test_a_light_that_only_switches_has_no_settings`.
  - `test_a_one_temperature_thermostat_describes_its_limits_step_and_start`: `min_temp` 86, `max_temp` 125, no step, Fahrenheit gives `step == 1` and `start == 106` (the middle, 105.5, rounded to a step); with `temperature: 110` gives `start == 110`; with `target_temp_step: 0.5` gives `step == 0.5`.
  - `test_a_range_thermostat_describes_two_required_settings`: `climate.hall` (45 to 95, showing 65 and 72) gives `heat_to` start 65 and `cool_to` start 72, both `optional is False`; without the two shown numbers gives 62 and 78.
  - `test_a_thermostat_with_no_limits_gets_home_assistants_defaults`.
  - `test_celsius_uses_half_degree_steps`.
  - `test_step_detail` for the five sentences and `""` for a run step.
  - The existing "not offered" tests, pointed at `describe_device`.
- [ ] **Step 2:** Run the WSL command for `tests/ha/test_devices.py`. Expected: the new tests fail because `describe_device` doesn't exist.
- [ ] **Step 3:** Implement `describe_device` and `step_detail`.
- [ ] **Step 4:** Run `tests/ha/test_devices.py` in WSL. Expected: all pass.
- [ ] **Step 5:** Commit.

### Task 3: The checks read the description

**Files:**
- Modify: `custom_components/morning_routine/step_input.py` (`_check_device` only)
- Test: `tests/ha/test_device_steps.py`

**Consumes:** `describe_device` from Task 2.

`_check_device(hass, name, action, settings, number)` keeps its signature and every refusal it has today, and takes all its facts from the description:
- no description: `item_not_allowed`. An action the description doesn't list: `action_not_offered`.
- a setting that is set and isn't one of the action's settings, or a setting that isn't optional and is missing: `invalid_step`.
- `brightness` that isn't a whole number or is outside the selector's `min` and `max`: `brightness_out_of_range`.
- any other setting outside its selector's `min` and `max`: `temperature_out_of_range`, with `low` and `high` from the selector.
- `set_temperature` with `heat_to` at or above `cool_to`: `heat_not_below_cool`.

- [ ] **Step 1: Write the failing tests.** One parametrized test, `test_the_description_and_the_checks_agree`, over `lamp`, a light that only switches, `heater` and `hall`. For every action in the description:
  - every setting at its `min` and at its `max` is accepted (for `hall`: `heat_to` at `min` with `cool_to` at `max`);
  - a step that carries every `start` value is accepted, so a new step can be saved without moving a slider;
  - each setting one below `min` and one above `max` is refused;
  - a setting key the action doesn't list is refused;
  - a value between steps (68.3 on `hall`) is accepted.
  Also `test_a_thermostat_with_no_limits_is_checked_against_the_defaults`.
- [ ] **Step 2:** Run in WSL. Expected: the between-steps and start-value cases pass already; the no-limits test fails.
- [ ] **Step 3:** Rewrite `_check_device` to read `describe_device`.
- [ ] **Step 4:** Run all of `tests/ha` in WSL. Expected: every existing refusal test still passes.
- [ ] **Step 5:** Commit.

### Task 4: The view carries the descriptions and each step's detail

**Files:**
- Modify: `custom_components/morning_routine/view.py`, `custom_components/morning_routine/devices.py` (remove `device_info`)
- Test: `tests/ha/test_view.py`, `tests/ha/test_websocket.py`

**Produces (the view the card reads):**
- `items[n]`: `{"item", "name", "actions"}`. A labelled script, scene or automation has `RUN_ACTIONS`. A light or thermostat has `describe_device`'s list. The fields `type`, `brightness`, `temperature`, `min_temp` and `max_temp` are gone.
- `steps[n]`: as today without `type`, plus `"detail": step_detail(hass, step)`.
- `temperature_unit` is gone from the view. The unit is inside each selector and each detail line.

- [ ] **Step 1: Update the tests first:** `test_view_offers_lights_and_thermostats_without_a_label` expects the new item shape for a script, `hall`, `heater` and `lamp`. `test_view_shows_a_device_step_with_its_action_and_settings` expects `detail` ("Turn on at 40%" and "Heat to 68°F, cool to 74°F") and no `type`. `test_view_marks_a_device_step_whose_device_is_gone` expects the detail still written from the saved step.
- [ ] **Step 2:** Run in WSL, see them fail. Implement. Remove `device_info`. Run all of `tests/ha` in WSL. Expected: all pass.
- [ ] **Step 3:** Commit.

### Task 5: Card logic: the form's state

**Files:**
- Modify: `custom_components/morning_routine/www/morning-routine-card.js` (top half)
- Test: `tests/card/card-logic.test.mjs`

**Consumes:** the view from Task 4.

**Removed exports:** `stepDetail`, `chosenItem`, `searchItems`, `itemGroups`, `actionChoices`, `settingFields`, `settingsError`, `settingsOf`, and their tests. `formItems` keeps its job and tells a once-only item by `actions[0].action === "run"`.

**Produces (exports).** The form's state is one plain object, `{ editing, item, action, values, checked, locked }`. `values` maps a setting's key to a number. `checked` maps an optional setting's key to true or false. `locked` means only the time can change.

```js
actionOf(entry, action)          // that action's description, or null
canShow(entry, step)             // true when the description can draw this saved step
startForm(view, editingId)       // the state a form opens with
withItem(state, entry)           // the person chose an item
withAction(state, entry, action) // the person chose an action
withChecked(state, key, checked) // the person ticked or cleared an optional setting
withValue(state, key, value)     // the person moved a slider or typed in its box
refreshed(state, view)           // a new view arrived: { state, note }, note is null, "choice_gone" or "item_changed"
formStep(state, entry)           // { item, action, ...settings } to send, or null when nothing is chosen
```

Rules:
- A new step opens with nothing chosen: `item` is `""`, and `formStep` returns null.
- `canShow` is false when the step's action isn't offered, a saved setting isn't one of that action's settings, a required setting has no saved value, or a saved value is outside its selector's `min` and `max`.
- Editing opens `locked` when the step's item is gone or `canShow` is false. `formStep` then returns the saved action and saved settings unchanged.
- Editing a step that can be shown: each setting's value is the saved value, or its `start` when none is saved. An optional setting is checked only when it has a saved value.
- `withItem` takes the first action, every setting's `start`, and nothing checked. `withAction` keeps a value and a check the state already holds for the same key.
- `formStep` sends only the settings of the chosen action that are required or checked, each as the value held. A held value is never rounded.
- `refreshed`: the chosen item is no longer offered: `item` becomes `""`, note `"choice_gone"`. The chosen action is no longer offered: the first action and its starts, note `"item_changed"`. A setting is no longer offered: it is dropped. A new setting appears: it gets its `start`. A value that is drawn (required or checked) and now outside the limits moves to the nearest limit. Any of those three gives note `"item_changed"`. A `locked` state stays as it is.

- [ ] **Step 1: Write the failing tests**, with fixtures `LAMP`, `PLAIN`, `HEATER`, `HALL` and a script in the new item shape:
  - `startForm` for a new step, for a saved light step with brightness 40 (checked, value 40), and for one without brightness (unchecked, value is the start).
  - `canShow` for each of its four false cases, and true for a saved value between steps.
  - `startForm` is locked for an item that is gone and for a step the item can't show, and `formStep` then returns the saved fields.
  - **Review Focus 3:** `formStep(startForm(view, id), entry)` equals the saved step's fields for: `hall` holding 68.3 and 74; a light step with no brightness; a light step with brightness 40.
  - `withItem` on `HALL` then `formStep` gives `heat_to` and `cool_to` equal to the starts.
  - `withChecked` then `withValue` on `LAMP` sends the brightness; cleared again sends none.
  - `withAction` to "turn_off" and back keeps the brightness value and its check.
  - **Review Focus 2:** `refreshed` when the lamp stops dimming drops brightness, gives `"item_changed"`, and `formStep` sends no brightness. `refreshed` when the item is gone gives `"choice_gone"` and `formStep` is null. `refreshed` when limits narrow moves a drawn value to the limit and gives `"item_changed"`. `refreshed` with nothing different gives a null note and an equal state.
- [ ] **Step 2:** Run `node --test "tests/card/*.test.mjs"`. Expected: the new tests fail on missing exports.
- [ ] **Step 3:** Implement. Delete the removed exports and their tests.
- [ ] **Step 4:** Run the card tests. Expected: all pass. The element's form is broken until Task 7; `card-element.test.mjs` doesn't open the form, so it still passes.
- [ ] **Step 5:** Commit.

### Task 6: The card's face uses Home Assistant's switch and dropdown

**Files:**
- Modify: `custom_components/morning_routine/www/morning-routine-card.js` (element)
- Test: `tests/card/card-element.test.mjs`

**Consumes:** the loading recipe from Task 1.

**Produces:**
- `loadControls()`: runs the recipe once per page and resolves to true when `ha-selector`, `ha-switch`, `ha-checkbox`, `ha-formfield` and `ha-button` are defined (less any that Task 1 ruled out), or false after 5 seconds or on any error. It never throws.
- The card starts `loadControls()` when it first connects and draws itself again when it settles.
- `_switch(key, label, checked, change)` draws `ha-switch` when that element is defined, and the card's own switch otherwise. Either way the switch shows the view's value: after a tap it is put back and `change(!checked)` is called, so it moves only when the next view says so.
- The clock dropdown is `ha-selector` with `{select: {mode: "dropdown", options}}` when the controls loaded, and the card's own `<select>` otherwise.
- Each step's detail line is `step.detail` from the view.

The fake elements in `card-element.test.mjs` grow just enough to test this: they keep their tag, properties and listeners, can be found by tag or `data-key`, and can fire an event. `customElements.get` answers for the tags a test says are defined.

- [ ] **Step 1: Write the failing tests:**
  - **Review Focus 1:** `with no Home Assistant controls the card draws its own switches and dropdown, and the routine switch sends the change`.
  - **Review Focus 1:** `a loader that throws or never answers leaves the card working` (advance the mocked clock 5 seconds).
  - `with ha-switch defined the card draws it, and a change sends the update and puts the switch back`.
  - `the card draws itself again with Home Assistant's controls once they load`.
  - `a step row shows the server's detail line`.
- [ ] **Step 2:** Run the card tests, see them fail. Implement. Run them. Expected: all pass, including the six connection tests.
- [ ] **Step 3:** Commit.

### Task 7: The form uses Home Assistant's controls

**Files:**
- Modify: `custom_components/morning_routine/www/morning-routine-card.js` (element), `tests/card/demo.html`
- Test: `tests/card/card-element.test.mjs`

**Consumes:** Task 5's functions, Task 6's `loadControls()`.

The form, top to bottom, as in the spec's sketch:
- Title "Add a step" or "Edit step".
- The picker: `ha-selector` with `{entity: {include_entities}}`, listing `formItems(view, editing)`. For a `locked` step the item's name is shown as text, with no picker.
- The action: `ha-selector` with `button_toggle`, only when the item has more than one action.
- One row for each setting of the chosen action. An optional setting gets `ha-checkbox` inside `ha-formfield` with the setting's name, and its slider only when checked. A required setting shows its name and its slider.
- "When": a number box for minutes (`{number: {min: 0, max: 720, mode: "box"}}`) and a dropdown with "before the alarm" and "after the alarm". `offsetError` still checks the minutes.
- A line for the form's sentence, then "Remove step" (when editing), Cancel (plain `ha-button`) and Save (filled `ha-button`).

Rules:
- The dialog stays the card's own `<dialog>`, styled to match Home Assistant's dialogs. There is no `<form>` element, so no key press submits anything. Save and Cancel act on click. (Review Focus 5)
- Every control's `value-changed` goes through one of Task 5's functions. The form's controls are drawn again only when the item, the action, a check, the list of settings, or a value changed by `refreshed` is different. A slider being dragged is never redrawn.
- Open controls get the newest `hass` whenever the card does.
- Save is off until an item is chosen. Save sends `withSaved(view, editing, { ...formStep(state, entry), offset_minutes })`.
- If the controls haven't loaded when the form opens, it waits for `loadControls()` and then shows either the form or the sentence.
- `demo.html`: its fake server sends the new view shape. It shows the card's face with the card's own controls, and its form shows the couldn't-load sentence.

New card text, for the owner to approve (also listed in `docs/status.md` in Task 8):
- "This form couldn't load Home Assistant's controls. Reload the page to try again."
- "This item changed while the form was open. Check the settings before saving."
- "What this step does can't be changed here, because the item no longer offers it. Its time can still be changed."
- "Turn on", "Turn off" and "Set temperatures" as button labels. "Heat to" and "Cool to" beside sliders.

- [ ] **Step 1: Write the failing element tests**, with fake controls defined:
  - `adding a light step with a brightness sends it`: choose the lamp, tick Brightness, set 40, Save. The message's last step is `{item: "light.lamp", offset_minutes: -30, action: "turn_on", brightness: 40, enabled: true}`.
  - `a light step with Brightness unticked sends no brightness`.
  - `a range thermostat can be saved without moving a slider`.
  - `Save is off until an item is chosen`.
  - **Review Focus 3:** `retiming a saved step sends its settings back unchanged`, for a step holding 68.3.
  - **Review Focus 2:** `a view that drops brightness while the form is open redraws the form, says so, and Save sends no brightness`.
  - **Review Focus 2:** `a view that removes the chosen item clears the choice and turns Save off`.
  - `a locked step shows its name and the sentence, and Save changes only its time`.
  - `the server's refusal sentence is shown in the form`.
  - **Review Focus 1:** `the form shows the couldn't-load sentence when the controls never load`.
- [ ] **Step 2:** Run the card tests, see them fail. Implement. Run them. Expected: all pass.
- [ ] **Step 3: Check it in the throwaway Home Assistant** (restart it first, so the server side of Tasks 2 to 4 is running). As `tester`: add a light step with brightness, add the same light turning off, add a one-temperature thermostat with and without a temperature, add a range thermostat, edit each, retime one, remove one, and cause one refusal ("heat to" at or above "cool to"). Check: nothing in the browser console, the saved steps match what was shown, the thermostat sliders use the device's limits and step, and pressing Enter in the minutes box and in a slider's number box doesn't save. (Review Focus 5)
- [ ] **Step 4:** Repeat the add and edit checks as `member`, 360 pixels wide, in the light theme and the dark theme. Keep one screenshot of the form for the owner, outside the repo. (Review Focus 4 and 5)
- [ ] **Step 5:** Commit.

### Task 8: Documents, version, final review

**Files:**
- Modify: `custom_components/morning_routine/manifest.json` (`"version": "0.4.0"`), `README.md` ("Use the card"), `docs/superpowers/specs/2026-11-01-morning-routine-integration-design.md` (one line in "The card" pointing to the Phase 4 spec), `docs/status.md`

- [ ] **Step 1:** Version 0.4.0. README describes the new form. `docs/status.md`: where Phase 4 stands, each decision made while building with what it costs if wrong, every new or changed piece of card text, and what was and wasn't checked in a browser.
- [ ] **Step 2:** Run all three suites. Commit.
- [ ] **Step 3:** One fresh reviewer on the most capable model reads the whole change with this plan, the spec and the Review Focus. Fix Critical and Important findings, each with a test that fails first. Record the rest in `docs/status.md`; none becomes an issue without the owner.
- [ ] **Step 4:** Write the hand-off. Nothing is pushed.

## After this plan, each needing the owner's go

1. Push `main`.
2. Update the integration on the owner's server to 0.4.0 and restart, following the rules in the owner's private repo.
3. The owner tries the form on the owner's dashboard, as the owner and as a household member, on a phone.

## Later phases

### More device types
Switches, fans and the rest. With this phase done, a new type is mostly a new description in `devices.py`.

### Motion steps
Run a step on the next motion after a set time. Waits for a sensor that works while people are home.

### Release
Check the card on real phones and publish a release.
