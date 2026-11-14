import assert from "node:assert/strict";
import { test } from "node:test";

import {
  actionOf,
  canShow,
  formEntry,
  formItems,
  formStep,
  joinOffset,
  offsetError,
  offsetLabel,
  problemText,
  refreshed,
  sortSteps,
  splitOffset,
  startForm,
  timelineRows,
  withAction,
  withChecked,
  withItem,
  withRemoved,
  withSaved,
  withToggled,
  withValue,
} from "../../custom_components/morning_routine/www/morning-routine-card.js";

// A step as the server's view sends it. A script's id is its item.
const step = (item, offset_minutes, extra = {}) => ({
  id: item,
  item,
  name: item,
  offset_minutes,
  enabled: true,
  available: true,
  action: "run",
  brightness: null,
  temperature: null,
  heat_to: null,
  cool_to: null,
  detail: "",
  ...extra,
});

const wire = (item, offset_minutes, enabled = true, extra = {}) => ({
  id: item,
  item,
  offset_minutes,
  enabled,
  action: "run",
  ...extra,
});

// Items as the server's view sends them: what a step can do, with each setting as a selector.
const slider = (min, max, unit, stepSize = 1) => ({
  number: { min, max, step: stepSize, mode: "slider", unit_of_measurement: unit },
});
const BRIGHTNESS = {
  key: "brightness",
  name: "Brightness",
  optional: true,
  hint: "as it was",
  start: 100,
  selector: slider(1, 100, "%"),
};
const TURN_OFF = { action: "turn_off", name: "Turn off", settings: [] };
const script = (item, name) => ({ item, name, actions: [{ action: "run", name: "Run", settings: [] }] });
const LAMP = {
  item: "light.lamp",
  name: "Lamp",
  actions: [{ action: "turn_on", name: "Turn on", settings: [BRIGHTNESS] }, TURN_OFF],
};
const PLAIN = {
  item: "light.plain",
  name: "Plain",
  actions: [{ action: "turn_on", name: "Turn on", settings: [] }, TURN_OFF],
};
const HEATER = {
  item: "climate.heater",
  name: "Heater",
  actions: [
    {
      action: "turn_on",
      name: "Turn on",
      settings: [
        {
          key: "temperature",
          name: "Temperature",
          optional: true,
          hint: "last setting",
          start: 106,
          selector: slider(86, 125, "°F"),
        },
      ],
    },
    TURN_OFF,
  ],
};
const HALL = {
  item: "climate.hall",
  name: "Hall",
  actions: [
    {
      action: "set_temperature",
      name: "Set temperatures",
      settings: [
        { key: "heat_to", name: "Heat to", optional: false, start: 62, selector: slider(45, 95, "°F") },
        { key: "cool_to", name: "Cool to", optional: false, start: 78, selector: slider(45, 95, "°F") },
      ],
    },
  ],
};
const lampStep = (id, offset_minutes, extra = {}) =>
  step("light.lamp", offset_minutes, { id, name: "Lamp", action: "turn_on", detail: "Turn on", ...extra });
const hallStep = (id, heat_to, cool_to) =>
  step("climate.hall", -20, { id, name: "Hall", action: "set_temperature", heat_to, cool_to });

const viewOf = (steps, items = []) => ({
  steps,
  items,
  min_offset_minutes: -720,
  max_offset_minutes: 60,
});

test("offsetLabel", () => {
  assert.equal(offsetLabel(0), "At alarm");
  assert.equal(offsetLabel(-30), "30 min before");
  assert.equal(offsetLabel(45), "45 min after");
  assert.equal(offsetLabel(-60), "1 hr before");
  assert.equal(offsetLabel(-90), "1 hr 30 min before");
  assert.equal(offsetLabel(-720), "12 hr before");
  assert.equal(offsetLabel(60), "1 hr after");
  assert.equal(offsetLabel(-1), "1 min before");
});

test("sortSteps orders by offset, then by name ignoring case, and leaves its input alone", () => {
  const steps = [
    step("script.c", 0, { name: "banana" }),
    step("script.a", -30, { name: "Zebra" }),
    step("script.b", 0, { name: "Apple" }),
  ];
  const sorted = sortSteps(steps);
  assert.deepEqual(sorted.map((s) => s.item), ["script.a", "script.b", "script.c"]);
  assert.equal(steps[0].item, "script.c");
});

test("timelineRows puts at-alarm steps after the alarm row", () => {
  const rows = timelineRows([step("script.after", 10), step("script.at", 0), step("script.before", -30)]);
  assert.deepEqual(
    rows.map((row) => (row.type === "alarm" ? "alarm" : row.step.item)),
    ["script.before", "alarm", "script.at", "script.after"],
  );
});

test("timelineRows with only later steps starts with the alarm row", () => {
  const rows = timelineRows([step("script.after", 10)]);
  assert.deepEqual(rows.map((row) => row.type), ["alarm", "step"]);
});

test("timelineRows with no steps is only the alarm row", () => {
  assert.deepEqual(timelineRows([]), [{ type: "alarm" }]);
});

test("splitOffset", () => {
  assert.deepEqual(splitOffset(-30), { minutes: 30, direction: "before" });
  assert.deepEqual(splitOffset(45), { minutes: 45, direction: "after" });
  assert.deepEqual(splitOffset(0), { minutes: 0, direction: "before" });
});

test("joinOffset", () => {
  assert.equal(joinOffset(30, "before"), -30);
  assert.equal(joinOffset(45, "after"), 45);
});

test("joinOffset never returns negative zero", () => {
  assert.ok(Object.is(joinOffset(0, "before"), 0));
  assert.ok(Object.is(joinOffset(0, "after"), 0));
});

test("offsetError refuses letters, an empty box, 1.5 and -5", () => {
  const view = viewOf([]);
  for (const text of ["abc", "", "  ", "1.5", "-5", "3e1", "12x"]) {
    assert.equal(offsetError(text, "before", view), "Enter a whole number of minutes.", `for "${text}"`);
  }
});

test("offsetError allows 720 before and 60 after, and refuses 721 before and 61 after", () => {
  const view = viewOf([]);
  assert.equal(offsetError("720", "before", view), null);
  assert.equal(offsetError("60", "after", view), null);
  assert.equal(offsetError("0", "after", view), null);
  assert.equal(offsetError(" 30 ", "before", view), null);
  assert.equal(offsetError("721", "before", view), "A step can be at most 720 minutes before the alarm.");
  assert.equal(offsetError("61", "after", view), "A step can be at most 60 minutes after the alarm.");
});

test("offsetError takes its limits from the view", () => {
  const view = { ...viewOf([]), min_offset_minutes: -100, max_offset_minutes: 10 };
  assert.equal(offsetError("101", "before", view), "A step can be at most 100 minutes before the alarm.");
  assert.equal(offsetError("11", "after", view), "A step can be at most 10 minutes after the alarm.");
});

test("formItems leaves out scripts other steps use", () => {
  const items = [script("script.a", "A"), script("script.b", "B"), script("script.c", "C")];
  const view = viewOf([step("script.a", -30), step("script.b", 0)], items);
  assert.deepEqual(formItems(view, null), [items[2]]);
  assert.deepEqual(formItems(view, "script.a"), [items[0], items[2]]);
});

test("formItems always offers a light or thermostat, even one that is already a step", () => {
  const view = viewOf([lampStep("a", -30)], [LAMP, HEATER]);
  assert.deepEqual(formItems(view, null), [LAMP, HEATER]);
  assert.deepEqual(formItems(view, "a"), [LAMP, HEATER]);
});

test("formItems offers only what the server lists, so an edited step's own item that is gone is not in it", () => {
  const view = viewOf([step("script.gone", -30, { name: "Gone", available: false })], [script("script.c", "C")]);
  assert.deepEqual(formItems(view, "script.gone"), [script("script.c", "C")]);
});

test("withToggled changes one step and sends only what the server takes", () => {
  const view = viewOf([step("script.a", -30), step("script.b", 0)]);
  assert.deepEqual(withToggled(view, "script.b", false), [wire("script.a", -30), wire("script.b", 0, false)]);
});

test("withToggled keeps a step that is not available", () => {
  const view = viewOf([step("script.gone", -30, { available: false }), step("script.b", 0)]);
  assert.deepEqual(withToggled(view, "script.b", false), [wire("script.gone", -30), wire("script.b", 0, false)]);
});

test("withToggled changes only the step with that id when one light is two steps", () => {
  const view = viewOf([lampStep("a", -30, { brightness: 40 }), lampStep("b", 10, { action: "turn_off" })]);
  assert.deepEqual(withToggled(view, "b", false), [
    { id: "a", item: "light.lamp", offset_minutes: -30, enabled: true, action: "turn_on", brightness: 40 },
    { id: "b", item: "light.lamp", offset_minutes: 10, enabled: false, action: "turn_off" },
  ]);
});

test("withSaved adds a step that is enabled and has no id", () => {
  const view = viewOf([step("script.a", -30)]);
  assert.deepEqual(
    withSaved(view, null, { item: "light.lamp", offset_minutes: 15, action: "turn_on", brightness: 40 }),
    [wire("script.a", -30), { item: "light.lamp", offset_minutes: 15, action: "turn_on", brightness: 40, enabled: true }],
  );
});

test("withSaved keeps enabled false when retiming a step that is off", () => {
  const view = viewOf([step("script.a", -30, { enabled: false }), step("script.b", 0)]);
  assert.deepEqual(withSaved(view, "script.a", { item: "script.a", offset_minutes: 20, action: "run" }), [
    wire("script.a", 20, false),
    wire("script.b", 0),
  ]);
});

test("withSaved keeps the id when a step's time or settings change", () => {
  const view = viewOf([lampStep("a", -30, { brightness: 40 })]);
  assert.deepEqual(withSaved(view, "a", { item: "light.lamp", offset_minutes: -10, action: "turn_on" }), [
    { id: "a", item: "light.lamp", offset_minutes: -10, action: "turn_on", enabled: true },
  ]);
});

test("withSaved drops the id when a step changes what it does", () => {
  const view = viewOf([lampStep("a", -30)]);
  assert.deepEqual(withSaved(view, "a", { item: "light.lamp", offset_minutes: -30, action: "turn_off" }), [
    { item: "light.lamp", offset_minutes: -30, action: "turn_off", enabled: true },
  ]);
  assert.deepEqual(withSaved(view, "a", { item: "script.b", offset_minutes: -30, action: "run" }), [
    { item: "script.b", offset_minutes: -30, action: "run", enabled: true },
  ]);
});

test("withRemoved removes only the step with that id", () => {
  const view = viewOf([lampStep("a", -30), lampStep("b", 10, { action: "turn_off" }), step("script.b", 0)]);
  assert.deepEqual(
    withRemoved(view, "a").map((entry) => entry.id),
    ["b", "script.b"],
  );
});

test("problemText has a sentence for every code the server sends", () => {
  assert.equal(
    problemText("sensor_missing"),
    "This phone's Next alarm sensor is turned off or missing. Turn it on in the Home Assistant Android app, under Settings, Companion app, Manage sensors.",
  );
  assert.equal(
    problemText("sensor_stale"),
    "The phone is reporting an alarm time that has already passed. This usually means the Next alarm sensor's Allow list is on. Turn the Allow list off in the Home Assistant Android app.",
  );
  assert.equal(problemText("no_clock"), "Choose a clock below. Nothing runs until one is chosen.");
  assert.equal(problemText("no_label"), null);
  assert.equal(problemText("something_new"), null);
});

test("withSaved changes only the edited step when one light is two steps", () => {
  const view = viewOf([lampStep("a", -30, { brightness: 10 }), lampStep("b", 0, { brightness: 100 })]);
  assert.deepEqual(
    withSaved(view, "b", { item: "light.lamp", offset_minutes: 5, action: "turn_on", brightness: 90 }),
    [
      { id: "a", item: "light.lamp", offset_minutes: -30, enabled: true, action: "turn_on", brightness: 10 },
      { id: "b", item: "light.lamp", offset_minutes: 5, action: "turn_on", brightness: 90, enabled: true },
    ],
  );
});

test("withSaved drops the id when only the item changes", () => {
  const view = viewOf([lampStep("a", -30)]);
  assert.deepEqual(withSaved(view, "a", { item: "light.plain", offset_minutes: -30, action: "turn_on" }), [
    { item: "light.plain", offset_minutes: -30, action: "turn_on", enabled: true },
  ]);
});

// ----- The form's state -----

const NEW_FORM = { editing: null, item: "", action: null, values: {}, checked: {}, locked: false };

test("actionOf finds an action's description, or null", () => {
  assert.equal(actionOf(LAMP, "turn_off"), TURN_OFF);
  assert.equal(actionOf(LAMP, "set_temperature"), null);
  assert.equal(actionOf(null, "turn_on"), null);
});

test("a new step's form opens with nothing chosen and nothing to send", () => {
  const view = viewOf([], [LAMP]);
  const state = startForm(view, null);
  assert.deepEqual(state, NEW_FORM);
  assert.equal(formEntry(view, state), null);
  assert.equal(formStep(state, null), null);
});

test("editing a light step with a brightness opens with it ticked at the saved value", () => {
  const view = viewOf([lampStep("a", -30, { brightness: 40 })], [LAMP]);
  assert.deepEqual(startForm(view, "a"), {
    editing: "a",
    item: "light.lamp",
    action: "turn_on",
    values: { brightness: 40 },
    checked: { brightness: true },
    locked: false,
  });
});

test("editing a light step with no brightness opens with it unticked, holding the start value", () => {
  const view = viewOf([lampStep("a", -30)], [LAMP]);
  const state = startForm(view, "a");
  assert.deepEqual(state.values, { brightness: 100 });
  assert.deepEqual(state.checked, { brightness: false });
});

test("canShow is false for an action, a setting or a value the item doesn't offer", () => {
  assert.equal(canShow(LAMP, lampStep("a", 0, { action: "set_temperature" })), false);
  assert.equal(canShow(PLAIN, lampStep("a", 0, { brightness: 40 })), false);
  assert.equal(canShow(HALL, hallStep("a", 68, null)), false);
  assert.equal(canShow(HALL, hallStep("a", 40, 74)), false);
  assert.equal(canShow(HEATER, step("climate.heater", 0, { action: "turn_on", temperature: 130 })), false);
});

test("canShow is true for a saved value between slider steps, and for an optional setting left out", () => {
  assert.equal(canShow(HALL, hallStep("a", 68.3, 74)), true);
  assert.equal(canShow(LAMP, lampStep("a", 0)), true);
  assert.equal(canShow(LAMP, lampStep("a", 0, { brightness: 40 })), true);
});

test("a step whose item is gone opens locked and sends its saved fields back", () => {
  const view = viewOf([lampStep("a", -30, { brightness: 40, available: false })], [HEATER]);
  const state = startForm(view, "a");
  assert.equal(state.locked, true);
  assert.equal(formEntry(view, state), null);
  assert.deepEqual(formStep(state, null), { item: "light.lamp", action: "turn_on", brightness: 40 });
});

test("a step the item can no longer show opens locked and sends its saved fields back", () => {
  const view = viewOf([lampStep("a", -30, { brightness: 40 })], [{ ...PLAIN, item: "light.lamp" }]);
  const state = startForm(view, "a");
  assert.equal(state.locked, true);
  assert.deepEqual(formStep(state, formEntry(view, state)), { item: "light.lamp", action: "turn_on", brightness: 40 });
});

// Review Focus 3: opening a saved step and saving it sends back exactly what was saved.
test("a saved step opened and saved untouched sends the same settings", () => {
  const cases = [
    [hallStep("a", 68.3, 74), { item: "climate.hall", action: "set_temperature", heat_to: 68.3, cool_to: 74 }],
    [lampStep("a", -30), { item: "light.lamp", action: "turn_on" }],
    [lampStep("a", -30, { brightness: 40 }), { item: "light.lamp", action: "turn_on", brightness: 40 }],
    [lampStep("a", -30, { action: "turn_off" }), { item: "light.lamp", action: "turn_off" }],
    [step("script.a", -30), { item: "script.a", action: "run" }],
  ];
  for (const [saved, sent] of cases) {
    const view = viewOf([saved], [LAMP, HALL, script("script.a", "A")]);
    const state = startForm(view, saved.id);
    assert.equal(state.locked, false);
    assert.deepEqual(formStep(state, formEntry(view, state)), sent);
  }
});

test("choosing a range thermostat can be saved without moving a slider", () => {
  const state = withItem(NEW_FORM, HALL);
  assert.deepEqual(formStep(state, HALL), {
    item: "climate.hall",
    action: "set_temperature",
    heat_to: 62,
    cool_to: 78,
  });
});

test("choosing an item takes its first action, with nothing ticked", () => {
  const state = withItem(NEW_FORM, LAMP);
  assert.equal(state.action, "turn_on");
  assert.deepEqual(state.checked, { brightness: false });
  assert.deepEqual(formStep(state, LAMP), { item: "light.lamp", action: "turn_on" });
});

test("choosing another item keeps nothing from the one before", () => {
  const lamp = withValue(withChecked(withItem(NEW_FORM, LAMP), BRIGHTNESS, true), "brightness", 40);
  const state = withItem(lamp, HEATER);
  assert.deepEqual(state.values, { temperature: 106 });
  assert.deepEqual(state.checked, { temperature: false });
});

test("choosing nothing clears the choice", () => {
  const state = withItem(withItem(NEW_FORM, LAMP), null);
  assert.deepEqual(state, NEW_FORM);
});

test("ticking Brightness and moving the slider sends it, and unticking sends none", () => {
  let state = withItem(NEW_FORM, LAMP);
  state = withChecked(state, BRIGHTNESS, true);
  state = withValue(state, "brightness", 40);
  assert.deepEqual(formStep(state, LAMP), { item: "light.lamp", action: "turn_on", brightness: 40 });
  state = withChecked(state, BRIGHTNESS, false);
  assert.deepEqual(formStep(state, LAMP), { item: "light.lamp", action: "turn_on" });
});

test("switching to Turn off and back keeps the brightness and its tick", () => {
  let state = withValue(withChecked(withItem(NEW_FORM, LAMP), BRIGHTNESS, true), "brightness", 40);
  state = withAction(state, LAMP, "turn_off");
  assert.deepEqual(formStep(state, LAMP), { item: "light.lamp", action: "turn_off" });
  state = withAction(state, LAMP, "turn_on");
  assert.deepEqual(formStep(state, LAMP), { item: "light.lamp", action: "turn_on", brightness: 40 });
});

test("an emptied number box holds no number, and nothing can be sent until it has one", () => {
  let state = withChecked(withItem(NEW_FORM, LAMP), BRIGHTNESS, true);
  state = withValue(state, "brightness", undefined);
  assert.equal(state.values.brightness, null);
  assert.equal(formStep(state, LAMP), null);
  // Unticked, the empty box isn't drawn, so the step can be saved without a brightness.
  state = withChecked(state, BRIGHTNESS, false);
  assert.deepEqual(formStep(state, LAMP), { item: "light.lamp", action: "turn_on" });
  // Ticked again, the slider starts over at its start value.
  state = withChecked(state, BRIGHTNESS, true);
  assert.deepEqual(formStep(state, LAMP), { item: "light.lamp", action: "turn_on", brightness: 100 });
});

test("a value is sent as held, never rounded to the slider's step", () => {
  const state = withValue(withItem(NEW_FORM, HALL), "heat_to", 70.5);
  assert.equal(formStep(state, HALL).heat_to, 70.5);
});

// Review Focus 2: a new view arrives while the form is open.
test("refreshed with nothing different changes nothing and says nothing", () => {
  const view = viewOf([], [LAMP]);
  const state = withValue(withChecked(withItem(NEW_FORM, LAMP), BRIGHTNESS, true), "brightness", 40);
  assert.deepEqual(refreshed(state, view, viewOf([], [LAMP])), { state, note: null });
});

test("refreshed leaves a typed value outside the limits alone when the limits didn't change", () => {
  const view = viewOf([], [LAMP]);
  const state = withValue(withChecked(withItem(NEW_FORM, LAMP), BRIGHTNESS, true), "brightness", 250);
  assert.deepEqual(refreshed(state, view, viewOf([], [LAMP])), { state, note: null });
});

test("refreshed when the light stops dimming drops the brightness and says the item changed", () => {
  const state = withValue(withChecked(withItem(NEW_FORM, LAMP), BRIGHTNESS, true), "brightness", 40);
  const after = viewOf([], [{ ...PLAIN, item: "light.lamp" }]);
  const result = refreshed(state, viewOf([], [LAMP]), after);
  assert.equal(result.note, "item_changed");
  assert.deepEqual(formStep(result.state, formEntry(after, result.state)), { item: "light.lamp", action: "turn_on" });
});

test("refreshed when the chosen item is gone clears the choice and says so", () => {
  const state = withItem(NEW_FORM, LAMP);
  const result = refreshed(state, viewOf([], [LAMP]), viewOf([], [HEATER]));
  assert.equal(result.note, "choice_gone");
  assert.equal(result.state.item, "");
  assert.equal(formStep(result.state, null), null);
});

test("refreshed when another step takes the chosen script clears the choice", () => {
  const items = [script("script.a", "A")];
  const state = withItem(NEW_FORM, items[0]);
  const result = refreshed(state, viewOf([], items), viewOf([step("script.a", 0)], items));
  assert.equal(result.note, "choice_gone");
  assert.equal(result.state.item, "");
});

test("refreshed when the chosen action is no longer offered takes the first action and says the item changed", () => {
  const state = withAction(withItem(NEW_FORM, LAMP), LAMP, "turn_off");
  const after = viewOf([], [{ ...LAMP, actions: [LAMP.actions[0]] }]);
  const result = refreshed(state, viewOf([], [LAMP]), after);
  assert.equal(result.note, "item_changed");
  assert.equal(result.state.action, "turn_on");
});

test("refreshed when the limits narrow moves a drawn value to the limit and says the item changed", () => {
  const state = withItem(NEW_FORM, HALL);
  const narrow = { ...HALL.actions[0].settings[1], selector: slider(45, 75, "°F") };
  const after = viewOf([], [{ ...HALL, actions: [{ ...HALL.actions[0], settings: [HALL.actions[0].settings[0], narrow] }] }]);
  const result = refreshed(state, viewOf([], [HALL]), after);
  assert.equal(result.note, "item_changed");
  assert.equal(result.state.values.cool_to, 75);
});

test("refreshed moves a value that isn't drawn into new limits without a word", () => {
  const state = withValue(withItem(NEW_FORM, HEATER), "temperature", 120);
  const narrow = { ...HEATER.actions[0].settings[0], selector: slider(86, 110, "°F") };
  const after = viewOf([], [{ ...HEATER, actions: [{ ...HEATER.actions[0], settings: [narrow] }, TURN_OFF] }]);
  const result = refreshed(state, viewOf([], [HEATER]), after);
  assert.equal(result.note, null);
  assert.equal(result.state.values.temperature, 110);
});

test("refreshed says the item changed when a drawn slider's selector changes", () => {
  const state = withItem(NEW_FORM, HALL);
  const finer = HALL.actions[0].settings.map((setting) => ({ ...setting, selector: slider(45, 95, "°F", 0.5) }));
  const after = viewOf([], [{ ...HALL, actions: [{ ...HALL.actions[0], settings: finer }] }]);
  assert.equal(refreshed(state, viewOf([], [HALL]), after).note, "item_changed");
});

test("refreshed gives a setting that appears its start value and says the item changed", () => {
  const before = viewOf([], [{ ...PLAIN, item: "light.lamp" }]);
  const state = withItem(NEW_FORM, before.items[0]);
  const result = refreshed(state, before, viewOf([], [LAMP]));
  assert.equal(result.note, "item_changed");
  assert.deepEqual(result.state.values, { brightness: 100 });
  assert.deepEqual(result.state.checked, { brightness: false });
});

test("refreshed reads a locked step's saved settings again and stays locked", () => {
  const before = viewOf([lampStep("a", -30, { brightness: 40, available: false })], []);
  const state = startForm(before, "a");
  const after = viewOf([lampStep("a", -30, { brightness: 60, available: false })], [LAMP]);
  const result = refreshed(state, before, after);
  assert.equal(result.note, null);
  assert.equal(result.state.locked, true);
  assert.deepEqual(formStep(result.state, null), { item: "light.lamp", action: "turn_on", brightness: 60 });
});
