import assert from "node:assert/strict";
import { test } from "node:test";

import {
  chosenItem,
  formItems,
  joinOffset,
  offsetError,
  offsetLabel,
  problemText,
  sortSteps,
  splitOffset,
  timelineRows,
  withRemoved,
  withSaved,
  withToggled,
} from "../../custom_components/morning_routine/www/morning-routine-card.js";

const step = (item, offset_minutes, extra = {}) => ({
  item,
  name: item,
  offset_minutes,
  enabled: true,
  available: true,
  ...extra,
});

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

test("formItems leaves out items other steps use", () => {
  const items = [
    { item: "script.a", name: "A" },
    { item: "script.b", name: "B" },
    { item: "script.c", name: "C" },
  ];
  const view = viewOf([step("script.a", -30), step("script.b", 0)], items);
  assert.deepEqual(formItems(view, null), [{ item: "script.c", name: "C" }]);
  assert.deepEqual(formItems(view, "script.a"), [
    { item: "script.a", name: "A" },
    { item: "script.c", name: "C" },
  ]);
});

test("formItems keeps the edited step's own item when it is no longer available", () => {
  const view = viewOf(
    [step("script.gone", -30, { name: "Gone", available: false })],
    [{ item: "script.c", name: "C" }],
  );
  assert.deepEqual(formItems(view, "script.gone"), [
    { item: "script.gone", name: "Gone" },
    { item: "script.c", name: "C" },
  ]);
});

test("withToggled changes one step and sends only what the server takes", () => {
  const view = viewOf([step("script.a", -30), step("script.b", 0)]);
  assert.deepEqual(withToggled(view, "script.b", false), [
    { item: "script.a", offset_minutes: -30, enabled: true },
    { item: "script.b", offset_minutes: 0, enabled: false },
  ]);
});

test("withToggled keeps a step that is not available", () => {
  const view = viewOf([step("script.gone", -30, { available: false }), step("script.b", 0)]);
  assert.deepEqual(withToggled(view, "script.b", false), [
    { item: "script.gone", offset_minutes: -30, enabled: true },
    { item: "script.b", offset_minutes: 0, enabled: false },
  ]);
});

test("withSaved adds a step that is enabled", () => {
  const view = viewOf([step("script.a", -30)]);
  assert.deepEqual(withSaved(view, null, { item: "script.b", offset_minutes: 15 }), [
    { item: "script.a", offset_minutes: -30, enabled: true },
    { item: "script.b", offset_minutes: 15, enabled: true },
  ]);
});

test("withSaved keeps enabled false when retiming a step that is off", () => {
  const view = viewOf([step("script.a", -30, { enabled: false }), step("script.b", 0)]);
  assert.deepEqual(withSaved(view, "script.a", { item: "script.a", offset_minutes: 20 }), [
    { item: "script.a", offset_minutes: 20, enabled: false },
    { item: "script.b", offset_minutes: 0, enabled: true },
  ]);
});

test("withSaved can change a step's item", () => {
  const view = viewOf([step("script.a", -30)]);
  assert.deepEqual(withSaved(view, "script.a", { item: "script.b", offset_minutes: -30 }), [
    { item: "script.b", offset_minutes: -30, enabled: true },
  ]);
});

test("withRemoved", () => {
  const view = viewOf([step("script.a", -30), step("script.b", 0)]);
  assert.deepEqual(withRemoved(view, "script.a"), [{ item: "script.b", offset_minutes: 0, enabled: true }]);
});

test("problemText has a sentence for every code the server sends", () => {
  assert.equal(
    problemText("no_label"),
    'An admin needs to create a label named "morning routine" and add it to each script, scene or automation this routine may run.',
  );
  assert.equal(
    problemText("sensor_missing"),
    "This phone's Next alarm sensor is turned off or missing. Turn it on in the Home Assistant Android app, under Settings, Companion app, Manage sensors.",
  );
  assert.equal(
    problemText("sensor_stale"),
    "The phone is reporting an alarm time that has already passed. This usually means the Next alarm sensor's Allow list is on. Turn the Allow list off in the Home Assistant Android app.",
  );
  assert.equal(problemText("no_clock"), "Choose a clock below. Nothing runs until one is chosen.");
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
