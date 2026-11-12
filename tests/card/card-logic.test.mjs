import assert from "node:assert/strict";
import { test } from "node:test";

import {
  actionChoices,
  chosenItem,
  formItems,
  itemGroups,
  joinOffset,
  offsetError,
  offsetLabel,
  problemText,
  searchItems,
  settingFields,
  settingsError,
  settingsOf,
  sortSteps,
  splitOffset,
  stepDetail,
  timelineRows,
  withRemoved,
  withSaved,
  withToggled,
} from "../../custom_components/morning_routine/www/morning-routine-card.js";

// A step as the server's view sends it. A script's id is its item.
const step = (item, offset_minutes, extra = {}) => ({
  id: item,
  item,
  name: item,
  offset_minutes,
  enabled: true,
  available: true,
  type: "run",
  action: "run",
  brightness: null,
  temperature: null,
  heat_to: null,
  cool_to: null,
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

const LAMP = { item: "light.lamp", name: "Lamp", type: "light", actions: ["turn_on", "turn_off"], brightness: true };
const PLAIN = { item: "light.plain", name: "Plain", type: "light", actions: ["turn_on", "turn_off"], brightness: false };
const HEATER = {
  item: "climate.heater",
  name: "Heater",
  type: "thermostat",
  actions: ["turn_on", "turn_off"],
  temperature: true,
  min_temp: 86,
  max_temp: 125,
};
const HALL = {
  item: "climate.hall",
  name: "Hall",
  type: "thermostat_range",
  actions: ["set_temperature"],
  min_temp: 45,
  max_temp: 95,
};
const lampStep = (id, offset_minutes, extra = {}) =>
  step("light.lamp", offset_minutes, { id, name: "Lamp", type: "light", action: "turn_on", ...extra });

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
  const items = [
    { item: "script.a", name: "A", type: "run" },
    { item: "script.b", name: "B", type: "run" },
    { item: "script.c", name: "C", type: "run" },
  ];
  const view = viewOf([step("script.a", -30), step("script.b", 0)], items);
  assert.deepEqual(formItems(view, null), [items[2]]);
  assert.deepEqual(formItems(view, "script.a"), [items[0], items[2]]);
});

test("formItems always offers a light or thermostat, even one that is already a step", () => {
  const view = viewOf([lampStep("a", -30)], [LAMP, HEATER]);
  assert.deepEqual(formItems(view, null), [LAMP, HEATER]);
  assert.deepEqual(formItems(view, "a"), [LAMP, HEATER]);
});

test("formItems keeps the edited step's own item when it is no longer available", () => {
  const view = viewOf(
    [step("script.gone", -30, { name: "Gone", available: false })],
    [{ item: "script.c", name: "C", type: "run" }],
  );
  assert.deepEqual(formItems(view, "script.gone"), [
    { item: "script.gone", name: "Gone", type: "run" },
    { item: "script.c", name: "C", type: "run" },
  ]);
});

test("formItems keeps a device step's own item with no type when the device is gone", () => {
  const view = viewOf([lampStep("a", -30, { type: null, available: false })], [HEATER]);
  assert.deepEqual(formItems(view, "a"), [{ item: "light.lamp", name: "Lamp", type: null }, HEATER]);
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

test("stepDetail says what a light or thermostat step does", () => {
  assert.equal(stepDetail(step("script.a", 0), "°F"), "");
  assert.equal(stepDetail(lampStep("a", 0), "°F"), "Turn on");
  assert.equal(stepDetail(lampStep("a", 0, { brightness: 40 }), "°F"), "Turn on at 40%");
  assert.equal(stepDetail(lampStep("a", 0, { action: "turn_off" }), "°F"), "Turn off");
  assert.equal(stepDetail({ action: "turn_on", temperature: 115 }, "°F"), "Turn on at 115°F");
  assert.equal(
    stepDetail({ action: "set_temperature", heat_to: 68, cool_to: 74.5 }, "°F"),
    "Heat to 68°F, cool to 74.5°F",
  );
  assert.equal(stepDetail({ action: "turn_on", temperature: 20 }, undefined), "Turn on at 20°");
});

test("searchItems keeps names that have every typed word, and always the chosen item", () => {
  const items = [LAMP, PLAIN, HEATER, { item: "light.kitchen_lamp", name: "Kitchen Lamp", type: "light" }];
  assert.deepEqual(searchItems(items, "", "").length, 4);
  assert.deepEqual(
    searchItems(items, "lamp", "").map((entry) => entry.name),
    ["Lamp", "Kitchen Lamp"],
  );
  assert.deepEqual(
    searchItems(items, "  LAMP kit ", "").map((entry) => entry.name),
    ["Kitchen Lamp"],
  );
  assert.deepEqual(
    searchItems(items, "kitchen", "climate.heater").map((entry) => entry.name),
    ["Heater", "Kitchen Lamp"],
  );
  assert.deepEqual(searchItems(items, "zzz", ""), []);
});

test("itemGroups puts lights, then thermostats, then scripts, and leaves out empty groups", () => {
  const script = { item: "script.a", name: "A", type: "run" };
  const gone = { item: "light.gone", name: "Gone", type: null };
  assert.deepEqual(itemGroups([script, HALL, LAMP, HEATER, gone]), [
    { title: "", items: [gone] },
    { title: "Lights", items: [LAMP] },
    { title: "Thermostats", items: [HALL, HEATER] },
    { title: "Scripts, scenes and automations", items: [script] },
  ]);
  assert.deepEqual(itemGroups([script]), [{ title: "Scripts, scenes and automations", items: [script] }]);
  assert.deepEqual(itemGroups([]), []);
});

test("actionChoices names what a device can do", () => {
  assert.deepEqual(actionChoices(LAMP), [
    { action: "turn_on", text: "Turn on" },
    { action: "turn_off", text: "Turn off" },
  ]);
  assert.deepEqual(actionChoices(HALL), [{ action: "set_temperature", text: "Set temperatures" }]);
  assert.deepEqual(actionChoices({ item: "script.a", name: "A", type: "run" }), []);
  assert.deepEqual(actionChoices(null), []);
});

test("settingFields shows only the boxes the item and action take", () => {
  assert.deepEqual(settingFields(LAMP, "turn_on"), ["brightness"]);
  assert.deepEqual(settingFields(LAMP, "turn_off"), []);
  assert.deepEqual(settingFields(PLAIN, "turn_on"), []);
  assert.deepEqual(settingFields(HEATER, "turn_on"), ["temperature"]);
  assert.deepEqual(settingFields(HEATER, "turn_off"), []);
  assert.deepEqual(settingFields({ ...HEATER, temperature: false }, "turn_on"), []);
  assert.deepEqual(settingFields(HALL, "set_temperature"), ["heat_to", "cool_to"]);
  assert.deepEqual(settingFields(null, "turn_on"), []);
});

test("settingsError allows an empty brightness and refuses one outside 1 to 100", () => {
  const sentence = "Enter a brightness from 1 to 100, or leave it empty.";
  for (const text of ["", " ", "1", "100", " 40 "]) {
    assert.equal(settingsError(LAMP, "turn_on", { brightness: text }), null, `for "${text}"`);
  }
  for (const text of ["0", "101", "40.5", "-5", "abc", "4e1"]) {
    assert.equal(settingsError(LAMP, "turn_on", { brightness: text }), sentence, `for "${text}"`);
  }
});

test("settingsError checks an optional temperature against the device's range", () => {
  const sentence = "Enter a temperature from 86 to 125, or leave it empty.";
  for (const text of ["", "86", "125", "99.5"]) {
    assert.equal(settingsError(HEATER, "turn_on", { temperature: text }), null, `for "${text}"`);
  }
  for (const text of ["85", "126", "hot", "1e2"]) {
    assert.equal(settingsError(HEATER, "turn_on", { temperature: text }), sentence, `for "${text}"`);
  }
  assert.equal(settingsError(HEATER, "turn_off", { temperature: "hot" }), null);
});

test("settingsError leaves the range out of the sentence when the device reports none", () => {
  const noRange = { ...HEATER, min_temp: null, max_temp: null };
  assert.equal(settingsError(noRange, "turn_on", { temperature: "500" }), null);
  assert.equal(
    settingsError(noRange, "turn_on", { temperature: "hot" }),
    "Enter a temperature, or leave it empty.",
  );
});

test("settingsError needs both temperatures of a range, with heat below cool", () => {
  const both = "Enter a temperature from 45 to 95 in both boxes.";
  assert.equal(settingsError(HALL, "set_temperature", { heat_to: "68", cool_to: "74" }), null);
  assert.equal(settingsError(HALL, "set_temperature", { heat_to: "", cool_to: "74" }), both);
  assert.equal(settingsError(HALL, "set_temperature", { heat_to: "68", cool_to: "" }), both);
  assert.equal(settingsError(HALL, "set_temperature", { heat_to: "44", cool_to: "74" }), both);
  assert.equal(settingsError(HALL, "set_temperature", { heat_to: "68", cool_to: "96" }), both);
  assert.equal(
    settingsError(HALL, "set_temperature", { heat_to: "74", cool_to: "68" }),
    '"Heat to" must be lower than "Cool to".',
  );
  assert.equal(
    settingsError(HALL, "set_temperature", { heat_to: "70", cool_to: "70" }),
    '"Heat to" must be lower than "Cool to".',
  );
});

test("settingsOf turns what was typed into numbers and leaves empty boxes out", () => {
  assert.deepEqual(settingsOf(LAMP, "turn_on", { brightness: " 40 " }), { brightness: 40 });
  assert.deepEqual(settingsOf(LAMP, "turn_on", { brightness: "" }), {});
  assert.deepEqual(settingsOf(LAMP, "turn_off", { brightness: "40" }), {});
  assert.deepEqual(settingsOf(HALL, "set_temperature", { heat_to: "68", cool_to: "74.5" }), {
    heat_to: 68,
    cool_to: 74.5,
  });
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

test("chosenItem starts a new form on the first item", () => {
  const items = [{ item: "script.a" }, { item: "script.b" }];
  assert.equal(chosenItem(items, null), "script.a");
  assert.equal(chosenItem([], null), "");
});

test("chosenItem keeps a choice that is still offered", () => {
  assert.equal(chosenItem([{ item: "script.a" }, { item: "script.b" }], "script.b"), "script.b");
});

test("chosenItem chooses nothing when the choice is gone, and never another item", () => {
  assert.equal(chosenItem([{ item: "script.a" }], "script.b"), "");
  assert.equal(chosenItem([{ item: "script.a" }], ""), "");
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
