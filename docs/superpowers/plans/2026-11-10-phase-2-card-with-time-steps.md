# Morning Routine, Phase 2: The Card with Time Steps. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Budget:** 1 session / ~500k tokens. The owner chose on 2026-11-10 to have one session build every task itself, with one fresh reviewer at the end. ~~About 1.2M tokens with a fresh agent and a fresh reviewer per task.~~

**Goal:** Anyone logged in can see a routine on a dashboard card and add, retime, turn off and remove its time steps from a phone, with no admin and no Developer tools.

**Architecture:** The integration serves one JavaScript file and tells Home Assistant to load it, so the card needs no manual dashboard resource. The card holds no state of its own: it subscribes to a "view" of one routine over WebSocket and redraws whenever the server sends a new one. Every change goes to the server as a command, the server checks it with the same rules the `set_steps` action uses, and the result comes back as a new view.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.0 or newer, `probatio`, `pytest`, `pytest-homeassistant-custom-component==0.13.371`. The card is one plain JavaScript module with no build step and no npm packages. Card logic tests use Node 24's built-in test runner (`node --test`).

**Spec:** `docs/superpowers/specs/2026-11-01-morning-routine-integration-design.md`. Read "The card", "Who can change what", "What a step can run", "Setup" and "Entities and events" before starting a task. `docs/status.md` has the Phase 1 rulings.

## Global Constraints

- Domain `morning_routine`. Home Assistant 2026.10.0 or newer. Schemas use `probatio`, not `voluptuous`.
- Public repo: no household names, addresses, entity IDs from the owner's house, real phone identifiers or household habits in code, docs, tests or commit messages. Made-up values only, such as `script.start_the_heater`.
- Python: snake_case, absolute imports (`from custom_components.morning_routine.const import DOMAIN`), `logger = logging.getLogger(__name__)` with %-style formatting, `T | None`, minimal docstrings. Use `type`, never `kind`.
- `rules.py` and `clocks.py` must never import `homeassistant`. This plan does not change either file.
- `strings.json` and `translations/en.json` must hold the same text. `tests/test_translations.py` compares them.
- **No red and no alarm-style coloring in the card.** A step that is off, a problem, or a refused change is information. Use the theme's `--primary-text-color`, `--secondary-text-color`, `--primary-color`, `--divider-color` and `--card-background-color`.
- **No clock times anywhere in the card,** and no "next alarm" line. Everything is relative to the alarm.
- The card is designed for a phone first, at 360 pixels wide.
- Commit straight to `main` with explicit paths: `git commit <paths> -F -`. A new file needs `git add -- <path>` first. The owner has authorized pushing this repo for this plan.
- Native Windows can't run Home Assistant. Locally, `pytest` runs the rules and translation tests and `node --test tests/card/` runs the card logic tests. `tests/ha` runs in GitHub Actions after a push. Read results with `gh run list --repo JohnPeltonen/ha-morning-routine --limit 5`.

## Decisions This Plan Adds to the Spec

The owner made the first one on 2026-11-10. The rest are the plan writer's calls.

- **Motion steps are left out.** The step form has no "next motion" choice. Also left out: offering clock apps from the sensor's past history, and refusing scripts that need input fields.
- **The `set_steps` action stays for now.** The spec calls it temporary. It is removed once the card has been used on real phones.
- **A step whose item is gone can stay on the list.** The server refuses a new step whose item lacks the label. It accepts a list that still contains such an item only if that item is already one of this routine's steps. Without this, one deleted script would make every other change fail.
- **The card is plain JavaScript in one file with native controls** (`<input>`, `<select>`, `<dialog>`). No framework and no build step. Home Assistant's own form elements aren't always loaded when a custom card needs them.
- **Card text is English only and lives in the card file.** Home Assistant has no translation path for custom card text.
- **The card is given a routine by its config entry id:** `type: custom:morning-routine-card`, `routine: <entry id>`. The card's settings form offers a picker.
- **The subtitle reads** "Runs around each alarm from the clock below, only when this phone is home". The spec's wording uses the person's name, which the routine doesn't store separately from its title.
- **"Well in the past"** for the stale-sensor problem means more than 90 minutes before now, the same limit the rules use.
- **The last write wins** when two people change the same routine at once. Each card always builds its change from the newest view it has received.
- **The integration version becomes 0.2.0.** The card's address carries the version, so browsers fetch the new file after an update.

## Review Focus

Each line has a test in the task named.

1. A step's script was deleted, and someone turns a different step off: the change saves, and the deleted step stays on the list, marked as not available. (Task 1, Task 5)
2. A non-admin account makes every change the card offers: on and off, skip, clock, add, retime, remove. (Task 3)
3. Home Assistant restarts, or the routine is reloaded, while the card is open: the card says the routine isn't available, then recovers by itself without a page reload. (Task 3, Task 6)
4. Two people have the card open and one changes the steps: the other card redraws, and its next change is built from the new list. (Task 3, Task 6)
5. Someone types letters, a negative number, or 61 minutes after the alarm into the form: the form says what's allowed in plain words and nothing is sent. The same values sent straight to the server are refused and change nothing. (Task 3, Task 5)

---

## File Structure

```
custom_components/morning_routine/
  step_input.py      NEW  checks a list of steps from a person. Moved from __init__.py
  view.py            NEW  builds the view of one routine that the card draws
  websocket.py       NEW  the three card commands
  card.py            NEW  serves the card file and tells Home Assistant to load it
  www/
    morning-routine-card.js   NEW  the card: pure logic at the top, the element below
  __init__.py        registers the commands and the card; imports parse_steps from step_input
  manifest.json      dependencies and version
tests/ha/
  test_service.py    one new test (Task 1)
  test_view.py       NEW
  test_websocket.py  NEW
  test_card.py       NEW
tests/card/
  card-logic.test.mjs  NEW  Node tests for the pure logic
  demo.html            NEW  the card with a fake server, for looking at it in a browser
.github/workflows/tests.yaml   a third job for the Node tests
```

## The view

Every task from 2 onward uses this shape. It is what the server sends and what the card draws.

```json
{
  "entry_id": "0123456789abcdef0123456789abcdef",
  "title": "Test Phone's morning routine",
  "is_on": true,
  "skip_next": false,
  "clock": "com.google.android.deskclock",
  "clock_options": [{"package": "com.google.android.deskclock", "name": "Google Clock"}],
  "steps": [
    {"item": "script.start_the_heater", "name": "Start the heater", "offset_minutes": -30, "enabled": true, "available": true}
  ],
  "items": [{"item": "script.start_the_heater", "name": "Start the heater"}],
  "problems": [],
  "min_offset_minutes": -720,
  "max_offset_minutes": 60
}
```

- `clock` is `null` until one is chosen.
- `steps` is in stored order. The card sorts it.
- `items` is every script, scene and automation that has the label now, sorted by name.
- `available` is false when the step's item has been deleted or has lost the label.
- `problems` holds zero or more of these codes, in this order: `no_label`, `sensor_missing`, `sensor_stale`, `no_clock`.

---

### Task 1: Let a routine keep a step whose item is gone

**Files:**
- Create: `custom_components/morning_routine/step_input.py`
- Modify: `custom_components/morning_routine/__init__.py`
- Test: `tests/ha/test_service.py`

**Interfaces:**
- Produces: `step_input.parse_steps(hass: HomeAssistant, raw: Any, keep: frozenset[str] = frozenset()) -> list[Step]` and `step_input.refuse(key: str, **placeholders: str) -> ServiceValidationError`. `keep` is the set of items already in the routine's steps.

- [ ] **Step 1: Write the failing tests** in `tests/ha/test_service.py`

```python
async def test_set_steps_keeps_a_step_whose_item_lost_its_label(hass, loaded, labeled_script, add_item):
    other = add_item("script.other_step")
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}, {"item": other, "offset_minutes": 0}])
    er.async_get(hass).async_update_entity(labeled_script, labels=set())

    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}, {"item": other, "offset_minutes": 0, "enabled": False}])

    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True), Step(other, 0, False)]


async def test_set_steps_still_refuses_a_new_unlabeled_item(hass, loaded, labeled_script, add_item):
    unlabeled = add_item("script.unlabeled", labeled=False)
    await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}])

    with pytest.raises(ServiceValidationError) as refused:
        await set_steps(hass, loaded.entry_id, [{"item": labeled_script, "offset_minutes": -30}, {"item": unlabeled, "offset_minutes": 0}])

    assert refused.value.translation_key == "item_not_allowed"
    assert loaded.runtime_data.steps == [Step(labeled_script, -30, True)]
```

- [ ] **Step 2: Move `parse_steps`, `_refuse` (renamed `refuse`) and `STEP_KEYS` from `__init__.py` to `step_input.py`.** No behavior change yet. `__init__.py` imports both from `step_input`.
- [ ] **Step 3: Add `keep`.** An item that fails `item_is_allowed` is accepted when it is in `keep`. Every other check is unchanged. The service passes `frozenset(step.item for step in routine.steps)`.
- [ ] **Step 4: Run `pytest -v` locally.** Expected: the rules and translation tests still pass (142).
- [ ] **Step 5: Commit, push, and read CI.** Expected: Tests and Hassfest succeed, with the two new tests passing.

### Task 2: Build the view

**Files:**
- Create: `custom_components/morning_routine/view.py`
- Test: `tests/ha/test_view.py`

**Interfaces:**
- Consumes: `Routine` properties `is_on`, `skip_next`, `clock`, `clock_options`, `steps`; `routine.item_is_allowed(hass, item)`; `const.LABEL_NAME`, `MIN_OFFSET_MINUTES`, `MAX_OFFSET_MINUTES`, `CONF_ALARM_SENSOR`; `rules.RECORD_KEPT`.
- Produces: `view.build_view(hass: HomeAssistant, entry: RoutineConfigEntry) -> dict[str, Any]`, returning exactly the shape in "The view" above.

Rules for the parts that need a decision:
- **A name** is the state's `name` if the item has a state, otherwise the entity registry's `name` or `original_name`, otherwise the entity id.
- **`sensor_missing`:** the alarm sensor has no entity registry entry, or its entry is disabled. A sensor that reports `unavailable` is not a problem: that is what a phone with no alarm set reports.
- **`sensor_stale`:** the sensor's state parses as a time more than `rules.RECORD_KEPT` before `dt_util.utcnow()`.
- **`no_label`:** no label named `LABEL_NAME` exists.
- **`no_clock`:** `routine.clock` is `None`.

- [ ] **Step 1: Write the failing tests.** Use the `loaded`, `labeled_script`, `add_item`, `phone` and `freezer` fixtures.

```python
async def test_view_of_a_new_routine(hass, loaded):
    view = build_view(hass, loaded)
    assert view["entry_id"] == loaded.entry_id
    assert view["title"] == "Test Phone's morning routine"
    assert (view["is_on"], view["skip_next"], view["clock"]) == (False, False, None)
    assert view["clock_options"] == [{"package": GOOGLE_CLOCK, "name": "Google Clock"}]
    assert view["steps"] == [] and view["items"] == []
    assert view["problems"] == ["no_label", "no_clock"]
    assert (view["min_offset_minutes"], view["max_offset_minutes"]) == (-720, 60)

async def test_view_lists_steps_and_labeled_items_by_name(hass, loaded, add_item): ...
    # two labeled items with states named "Zebra" and "Apple"; one is a step at -30
    # steps == [{"item": ..., "name": "Zebra", "offset_minutes": -30, "enabled": True, "available": True}]
    # [i["name"] for i in view["items"]] == ["Apple", "Zebra"]

async def test_view_marks_a_step_whose_item_lost_its_label(hass, loaded, labeled_script): ...
    # steps[0]["available"] is False, and the item is not in view["items"]

async def test_view_marks_a_step_whose_item_was_deleted(hass, loaded, labeled_script): ...
    # after er.async_remove: available is False and name == the entity id

async def test_view_says_the_sensor_is_missing_when_it_is_disabled(hass, loaded, phone): ...
async def test_view_does_not_call_an_unavailable_sensor_a_problem(hass, loaded, phone): ...
async def test_view_says_the_sensor_is_stale_after_90_minutes(hass, freezer, loaded, phone): ...
    # sensor shows ALARM; at ALARM + 90 min: no "sensor_stale"; at ALARM + 91 min: "sensor_stale"
async def test_view_has_no_clock_problem_once_a_clock_is_chosen(hass, loaded): ...
```

- [ ] **Step 2: Implement `build_view`.**
- [ ] **Step 3: Commit, push, and read CI.** Expected: success, 8 new tests passing.

### Task 3: The card's commands

**Files:**
- Create: `custom_components/morning_routine/websocket.py`
- Modify: `custom_components/morning_routine/__init__.py` (`async_setup` calls `websocket.async_register(hass)`), `strings.json`, `translations/en.json`
- Test: `tests/ha/test_websocket.py`

**Interfaces:**
- Consumes: `view.build_view`, `step_input.parse_steps`, `step_input.refuse`, `Routine.add_listener`, `async_set_steps`, `async_set_on`, `async_set_skip`, `async_set_clock`.
- Produces: `websocket.async_register(hass: HomeAssistant) -> None` and these commands. None of them uses `require_admin`.

| Command | Fields | Result |
|---|---|---|
| `morning_routine/subscribe` | `entry_id: str` | A subscription. The first event is `{"view": <view>}`, and another follows every change. |
| `morning_routine/set_steps` | `entry_id: str`, `steps: list` | `null`. Steps are `{"item", "offset_minutes", "enabled"}`, checked by `parse_steps` with `keep` set to the routine's current items. |
| `morning_routine/update` | `entry_id: str`, and any of `is_on: bool`, `skip_next: bool`, `clock: str` | `null`. Applied in the order clock, skip, on. |

- An `entry_id` that is unknown, belongs to another integration, or isn't loaded gets the error code `not_found`.
- A `clock` that isn't a key of `routine.clock_options` is refused with a new translated error, key `clock_not_offered`, text "That clock isn't offered for this phone."
- A refused `set_steps` reaches the card as Home Assistant's `home_assistant_error` with the same `translation_key` the action uses.
- **A new view is sent when** the routine notifies its listeners, when the entity registry changes (`er.EVENT_ENTITY_REGISTRY_UPDATED`), and when the label registry changes (`lr.EVENT_LABEL_REGISTRY_UPDATED`).
- **When the entry unloads,** each subscriber gets one last event, `{"unavailable": true}`, and its listeners are removed. Use `entry.async_on_unload`.
- Unsubscribing removes every listener.

- [ ] **Step 1: Write the failing tests.** Add a fixture `member_client` that opens a WebSocket client for the `household_member` user: create a refresh token with `hass.auth.async_create_refresh_token(user, CLIENT_ID)`, make an access token, and pass it to `hass_ws_client`.

```python
async def test_subscribe_sends_the_view_first(hass, loaded, member_client): ...
    # result success; next message event == {"view": build_view(hass, loaded)}
async def test_subscribe_refuses_an_unknown_routine(hass, member_client): ...        # error code "not_found"
async def test_non_admin_sets_steps_and_gets_a_new_view(hass, loaded, labeled_script, member_client): ...
    # after set_steps: routine.steps == [Step(labeled_script, -30, True)], and an event whose view has that step
async def test_set_steps_refuses_an_unlabeled_item_and_changes_nothing(...): ...     # error translation_key "item_not_allowed"
async def test_set_steps_refuses_61_minutes_after(...): ...                          # "offset_out_of_range"; steps unchanged
async def test_set_steps_keeps_a_step_whose_item_lost_its_label(...): ...            # same case as Task 1, through the command
async def test_non_admin_turns_the_routine_on_and_off(...): ...                      # update is_on True then False
async def test_non_admin_sets_skip(...): ...
async def test_non_admin_chooses_a_clock(...): ...                                   # update clock GOOGLE_CLOCK -> routine.clock
async def test_update_refuses_a_clock_that_is_not_offered(...): ...                  # "clock_not_offered"; clock unchanged
async def test_two_subscribers_both_hear_a_change(hass, loaded, labeled_script, member_client, hass_ws_client): ...
async def test_view_is_sent_again_when_an_item_gains_the_label(...): ...
async def test_subscriber_is_told_when_the_routine_unloads(...): ...                 # event == {"unavailable": True}
async def test_unsubscribe_removes_the_listeners(...): ...                           # len(routine._listeners) back to its count before subscribing
```

- [ ] **Step 2: Implement the three commands and `async_register`.** Add `clock_not_offered` under `exceptions` in both translation files.
- [ ] **Step 3: Run `pytest -v` locally.** Expected: translation tests pass.
- [ ] **Step 4: Commit, push, and read CI.** Expected: success, 14 new tests passing.

### Task 4: Serve the card and load it

**Files:**
- Create: `custom_components/morning_routine/card.py`, `custom_components/morning_routine/www/morning-routine-card.js` (a placeholder for now)
- Modify: `custom_components/morning_routine/__init__.py`, `manifest.json`
- Test: `tests/ha/test_card.py`

**Interfaces:**
- Produces: `card.CARD_URL = "/morning_routine/morning-routine-card.js"` and `card.async_register_card(hass: HomeAssistant) -> None`. The custom element name is `morning-routine-card`.

- `manifest.json`: add `"dependencies": ["frontend", "http"]` and set `"version": "0.2.0"`.
- `async_register_card` registers the file with `hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, <path>, False)])` and calls `frontend.add_extra_js_url(hass, f"{CARD_URL}?v={version}")`. The version comes from `await async_get_integration(hass, DOMAIN)`. `async_setup` awaits it once.
- The placeholder file defines `morning-routine-card` as an element that shows "Morning Routine". Task 5 replaces it.

- [ ] **Step 1: Write the failing tests**

```python
async def test_the_card_file_is_served(hass, hass_client, loaded):
    response = await (await hass_client()).get("/morning_routine/morning-routine-card.js")
    assert response.status == 200
    assert "morning-routine-card" in await response.text()

async def test_home_assistant_is_told_to_load_the_card(hass, loaded):
    urls = hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    assert "/morning_routine/morning-routine-card.js?v=0.2.0" in urls

async def test_a_second_routine_does_not_register_the_card_twice(hass, loaded, ...): ...
```

If `DATA_EXTRA_MODULE_URL` has a different name in the installed Home Assistant, read `homeassistant/components/frontend/__init__.py` and use what `add_extra_js_url` writes to.

- [ ] **Step 2: Implement.**
- [ ] **Step 3: Commit, push, and read CI.** Expected: Tests succeed with 3 new tests, and Hassfest accepts the manifest.

### Task 5: The card's logic

**Files:**
- Modify: `custom_components/morning_routine/www/morning-routine-card.js` (the top half: exported pure functions. The placeholder element stays below them, inside `if (globalThis.customElements) { ... }`, so Node can import the file.)
- Create: `tests/card/card-logic.test.mjs`
- Modify: `.github/workflows/tests.yaml` (a job named "Card tests": check out, set up Node 24, run `node --test tests/card/`. Use the current major version of `actions/setup-node`.)

**Interfaces:**
- Produces these exports. `wire steps` means a list of `{item, offset_minutes, enabled}`, which is what `morning_routine/set_steps` takes.

| Function | Returns |
|---|---|
| `offsetLabel(offsetMinutes)` | `"At alarm"` for 0. Otherwise `"30 min before"`, `"45 min after"`, `"1 hr before"`, `"1 hr 30 min before"`, `"12 hr before"`. |
| `sortSteps(steps)` | A new list, by `offset_minutes`, then by `name` ignoring case. |
| `timelineRows(steps)` | Sorted steps as `{type: "step", step}` rows, with one `{type: "alarm"}` row after the last step whose offset is below 0. Steps at 0 come after the alarm row. With no steps, only the alarm row. |
| `splitOffset(offsetMinutes)` | `{minutes, direction}`, where direction is `"before"` or `"after"`. 0 gives `{minutes: 0, direction: "before"}`. |
| `joinOffset(minutes, direction)` | The offset as a number. 0 is always `0`, never `-0`. |
| `offsetError(text, direction, view)` | `null` when fine. Otherwise one of the three sentences below. `text` is what the person typed. |
| `formItems(view, editingItem)` | The items the form offers: `view.items` without items other steps already use. When editing, the step's own item is included even if it is not available. |
| `withToggled(view, item, enabled)` | Wire steps, with that one step's `enabled` changed. |
| `withSaved(view, editingItem, {item, offset_minutes})` | Wire steps. `editingItem` null adds a step, enabled. Otherwise it replaces that step and keeps its `enabled`. |
| `withRemoved(view, item)` | Wire steps without that step. |
| `problemText(code)` | The sentence for a problem code, below. An unknown code gives `null`. |

Exact text, and none of it may change without the owner:

| Where | Text |
|---|---|
| `offsetError`, not a whole number, or negative | `Enter a whole number of minutes.` |
| `offsetError`, too far before | `A step can be at most 720 minutes before the alarm.` (the number comes from the view) |
| `offsetError`, too far after | `A step can be at most 60 minutes after the alarm.` (the number comes from the view) |
| `no_label` | `An admin needs to create a label named "morning routine" and add it to each script, scene or automation this routine may run.` |
| `sensor_missing` | `This phone's Next alarm sensor is turned off or missing. Turn it on in the Home Assistant Android app, under Settings, Companion app, Manage sensors.` |
| `sensor_stale` | `The phone is reporting an alarm time that has already passed. This usually means the Next alarm sensor's Allow list is on. Turn the Allow list off in the Home Assistant Android app.` |
| `no_clock` | `Choose a clock below. Nothing runs until one is chosen.` |

- [ ] **Step 1: Write the failing tests** with `node:test` and `node:assert/strict`. One test per row of the functions table, and these cases by name:

```js
test("offsetLabel", () => { /* 0, -30, 45, -60, -90, -720, 60 -> "1 hr after" */ });
test("timelineRows puts at-alarm steps after the alarm row", ...);
test("timelineRows with no steps is only the alarm row", ...);
test("joinOffset never returns negative zero", () => assert.ok(Object.is(joinOffset(0, "before"), 0)));
test("offsetError refuses letters, an empty box, 1.5 and -5", ...);
test("offsetError allows 720 before and 60 after, and refuses 721 before and 61 after", ...);
test("formItems leaves out items other steps use", ...);
test("formItems keeps the edited step's own item when it is no longer available", ...);
test("withToggled keeps a step that is not available", ...);          // Review Focus 1
test("withSaved adds a step that is enabled", ...);
test("withSaved keeps enabled false when retiming a step that is off", ...);
test("withSaved can change a step's item", ...);
test("withRemoved", ...);
test("problemText has a sentence for every code the server sends", ...); // no_label, sensor_missing, sensor_stale, no_clock
```

- [ ] **Step 2: Run `node --test tests/card/`.** Expected: every test fails, because the functions don't exist.
- [ ] **Step 3: Implement the functions.**
- [ ] **Step 4: Run `node --test tests/card/`.** Expected: all pass.
- [ ] **Step 5: Commit, push, and read CI.** Expected: the new Card tests job succeeds, and `tests/ha/test_card.py` still passes.

### Task 6: Draw the routine

**Files:**
- Modify: `custom_components/morning_routine/www/morning-routine-card.js` (replace the placeholder element)
- Create: `tests/card/demo.html`

**Interfaces:**
- Consumes: the Task 5 functions, and the Task 3 commands through `hass.connection.subscribeMessage(callback, {type: "morning_routine/subscribe", entry_id})` and `hass.connection.sendMessagePromise({type: ..., ...})`.
- Produces: the element `morning-routine-card`, with `setConfig(config)`, `set hass(hass)`, `getCardSize()`, `connectedCallback` and `disconnectedCallback`. Task 7 adds the form to the same class.

What the element does:
- **Layout** follows the spec's card drawing, top to bottom: the title with the routine's toggle; the subtitle; any problem sentences; the timeline from `timelineRows`; "+ Add a step" (Task 7 makes it work); "Skip next alarm" with its toggle; "Clock to watch" with a `<select>`.
- **A timeline row** shows `offsetLabel` on the left, a dot on a vertical line, the step's name, and the step's toggle. The alarm row shows a larger filled dot and the word "Alarm".
- **A step that is off** stays in place with its name and label in the secondary text color.
- **A step that is not available** shows this under its name: `No longer available. It was deleted or lost the "morning routine" label.` Its toggle is hidden.
- **With no clock chosen,** the `<select>` shows a first option, "Choose a clock", that can't be picked again once a clock is chosen.
- **Toggles and the clock picker send a command and don't change what's drawn themselves.** The card redraws when the next view arrives. While a command is in flight, the control is disabled.
- **A refused command** shows its `message` in a line under the timeline, in the secondary text color, until the next view arrives.
- **No `routine` in the config:** the card shows only `Choose a routine in this card's settings.`
- **Subscribing fails, or `{"unavailable": true}` arrives:** the card shows only the title it last knew (if any) and `This routine isn't available. It may have been removed.` It then tries to subscribe again every 10 seconds while it is on the page.
- **Leaving the page** (`disconnectedCallback`) unsubscribes and stops the retry timer. Coming back subscribes again.
- **Styles** live in the element's shadow root. Toggles are `<input type="checkbox" role="switch">` with an `aria-label` naming what they switch.

`tests/card/demo.html` loads the card file with a relative path and gives it a fake `hass` whose `connection` keeps a view in memory and answers the three commands. It has a row of buttons for these cases: "Three steps", "No label yet", "Problems", "A step that's gone", "Server refuses", "Routine goes away", "Second person changes steps". Serve it with `python -m http.server` from the repo root.

- [ ] **Step 1: Write `demo.html` with the fake connection and the seven cases.**
- [ ] **Step 2: Implement the element.**
- [ ] **Step 3: Run `node --test tests/card/`.** Expected: still all pass, because the element is inside the `customElements` check.
- [ ] **Step 4: Look at it.** Open `http://localhost:8000/tests/card/demo.html` at 360 pixels wide and go through all seven cases. Expected for each: it matches the description above, nothing is red, nothing overflows the card, and no clock time appears. "Routine goes away" must recover when the fake server brings the routine back (Review Focus 3). "Second person changes steps" must redraw without a click (Review Focus 4). Save a screenshot of each case for the review.
- [ ] **Step 5: Commit, push, and read CI.**

### Task 7: The step form, and the card's place in the dashboard editor

**Files:**
- Modify: `custom_components/morning_routine/www/morning-routine-card.js`, `tests/card/demo.html`

**Interfaces:**
- Consumes: `formItems`, `splitOffset`, `joinOffset`, `offsetError`, `withSaved`, `withRemoved`, and `morning_routine/set_steps`.

What it adds:
- **"+ Add a step"** opens a native `<dialog>` titled "Add a step". It is hidden when `formItems(view, null)` is empty. In that case, and when the `no_label` problem isn't showing, the card says: `Nothing else has the "morning routine" label. An admin can add the label to a script, scene or automation.`
- **Tapping a step's name** opens the same dialog titled "Edit step", filled in from the step.
- **The form's fields,** in order: "What should happen", a `<select>` of `formItems`; "When", a number box for minutes, the word "minutes", and a `<select>` of "before the alarm" and "after the alarm". A new step starts at 30 minutes before.
- **Buttons:** "Cancel" and "Save" for both, and "Remove step" when editing.
- **Save** runs `offsetError`. If it returns a sentence, the sentence shows under the minutes box and nothing is sent. Otherwise it sends `withSaved` and closes the dialog when the command succeeds. If the server refuses, the dialog stays open and shows the server's `message`.
- **Remove step** sends `withRemoved` and closes the dialog the same way.
- **If a new view arrives while the dialog is open,** the dialog stays open with what the person typed. Save still builds from the newest view (Review Focus 4). If the step being edited is no longer in the view, the dialog closes.
- **The dashboard editor:** `static getConfigForm()` returns `{schema: [{name: "routine", required: true, selector: {config_entry: {integration: "morning_routine"}}}]}`. `static getStubConfig()` returns `{routine: ""}`. The file adds `{type: "morning-routine-card", name: "Morning Routine", description: "Steps that run around a phone's alarm."}` to `window.customCards`.

- [ ] **Step 1: Add three demo cases:** "Add a step", "Edit a step", "Nothing left to add".
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run `node --test tests/card/`.** Expected: all pass.
- [ ] **Step 4: Look at it** at 360 pixels wide. Add a step, retime it to after the alarm, turn it off, edit it again and check it is still off, then remove it. Type `abc`, `-5`, `1.5` and `61` after: each shows its sentence and sends nothing (Review Focus 5). In "Server refuses", Save keeps the dialog open with the server's sentence. Save screenshots.
- [ ] **Step 5: Commit, push, and read CI.**

### Task 8: Documents, final review, and the owner's server

**Files:**
- Modify: `README.md`, `docs/status.md`

- [ ] **Step 1: Update `README.md`.** Replace "This version is set up by an admin" and the "Set the steps" section with how to add the card to a dashboard and use it. Say that anyone logged in can change steps. Keep the label instructions. Move `morning_routine.set_steps` to a short "For admins and scripts" section. Replace the HACS install steps with the Marketplace steps for Home Assistant 2026.11 and newer (Settings, Marketplace, Add from link), and keep one line for HACS on older versions. State that an update needs a restart.
- [ ] **Step 2: Update `docs/status.md`:** Phase 2 status, the decisions this plan added, and anything deferred.
- [ ] **Step 3: Final whole-branch review** by a fresh reviewer on the most capable model, from the commit before Task 1 to the head. Give it the spec, this plan, and the screenshots. Fix what breaks a guarantee in the spec or this plan. Other findings become proposed GitHub issues for the owner to confirm.
- [ ] **Step 4: Commit, push, and confirm CI is green on the final commit.**
- [ ] **Step 5 (needs the owner's approval, and follows the server rules in the owner's private repo): update the integration on the owner's server** through the Marketplace, and restart. Read back the version and the log.
- [ ] **Step 6 (with the owner): put the card on a test dashboard, not the generated House dashboard.** Check it on the owner's phone in the Home Assistant app, logged in as a non-admin account if one is available: the routine from Phase 1 appears with its test step, a step can be added, retimed, turned off and removed, and the dashboard editor offers the routine picker. Report what was not tested.

---

## Later phases

Each needs its own plan and its own go from the owner.

### Motion steps
The "next motion" choice in the form, the watch window, and the sensor picker. Waits for a motion sensor that works while people are home.

### Smaller items left out here
Offering clock apps from the sensor's past history, and refusing scripts that need input fields.

### Release
Remove the temporary `set_steps` action, put the routine cards on the owner's House dashboard through its generator, make a first GitHub release, and close the open items in `docs/status.md`.
