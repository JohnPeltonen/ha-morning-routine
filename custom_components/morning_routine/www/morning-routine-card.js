// The Morning Routine dashboard card.
// The top half is plain logic with no browser in it, so Node can test it.
// The element that draws the card is at the bottom.

const PROBLEM_TEXT = {
  no_label:
    'An admin needs to create a label named "morning routine" and add it to each script, scene or automation this routine may run.',
  sensor_missing:
    "This phone's Next alarm sensor is turned off or missing. Turn it on in the Home Assistant Android app, under Settings, Companion app, Manage sensors.",
  sensor_stale:
    "The phone is reporting an alarm time that has already passed. This usually means the Next alarm sensor's Allow list is on. Turn the Allow list off in the Home Assistant Android app.",
  no_clock: "Choose a clock below. Nothing runs until one is chosen.",
};

export function offsetLabel(offsetMinutes) {
  if (offsetMinutes === 0) return "At alarm";
  const total = Math.abs(offsetMinutes);
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  const parts = [];
  if (hours) parts.push(`${hours} hr`);
  if (minutes) parts.push(`${minutes} min`);
  return `${parts.join(" ")} ${offsetMinutes < 0 ? "before" : "after"}`;
}

export function sortSteps(steps) {
  return [...steps].sort(
    (a, b) =>
      a.offset_minutes - b.offset_minutes ||
      a.name.toLowerCase().localeCompare(b.name.toLowerCase()) ||
      a.item.localeCompare(b.item),
  );
}

export function timelineRows(steps) {
  const rows = [];
  let alarmPlaced = false;
  for (const step of sortSteps(steps)) {
    if (!alarmPlaced && step.offset_minutes >= 0) {
      rows.push({ type: "alarm" });
      alarmPlaced = true;
    }
    rows.push({ type: "step", step });
  }
  if (!alarmPlaced) rows.push({ type: "alarm" });
  return rows;
}

export function splitOffset(offsetMinutes) {
  return { minutes: Math.abs(offsetMinutes), direction: offsetMinutes > 0 ? "after" : "before" };
}

export function joinOffset(minutes, direction) {
  if (minutes === 0) return 0;
  return direction === "before" ? -minutes : minutes;
}

export function offsetError(text, direction, view) {
  const typed = String(text).trim();
  if (!/^\d+$/.test(typed)) return "Enter a whole number of minutes.";
  const minutes = Number(typed);
  const mostBefore = -view.min_offset_minutes;
  const mostAfter = view.max_offset_minutes;
  if (direction === "before" && minutes > mostBefore) {
    return `A step can be at most ${mostBefore} minutes before the alarm.`;
  }
  if (direction === "after" && minutes > mostAfter) {
    return `A step can be at most ${mostAfter} minutes after the alarm.`;
  }
  return null;
}

export function formItems(view, editingItem) {
  const usedByOthers = new Set(view.steps.map((step) => step.item).filter((item) => item !== editingItem));
  const items = view.items.filter((entry) => !usedByOthers.has(entry.item));
  if (editingItem !== null && !items.some((entry) => entry.item === editingItem)) {
    const own = view.steps.find((step) => step.item === editingItem);
    if (own) items.unshift({ item: own.item, name: own.name });
  }
  return items;
}

function wireSteps(view) {
  return view.steps.map((step) => ({
    item: step.item,
    offset_minutes: step.offset_minutes,
    enabled: step.enabled,
  }));
}

export function withToggled(view, item, enabled) {
  return wireSteps(view).map((step) => (step.item === item ? { ...step, enabled } : step));
}

export function withSaved(view, editingItem, { item, offset_minutes }) {
  const steps = wireSteps(view);
  if (editingItem === null) return [...steps, { item, offset_minutes, enabled: true }];
  return steps.map((step) => (step.item === editingItem ? { item, offset_minutes, enabled: step.enabled } : step));
}

export function withRemoved(view, item) {
  return wireSteps(view).filter((step) => step.item !== item);
}

export function problemText(code) {
  return PROBLEM_TEXT[code] ?? null;
}

if (globalThis.customElements) {
  class MorningRoutineCard extends HTMLElement {
    setConfig() {}

    connectedCallback() {
      this.textContent = "Morning Routine";
    }
  }
  customElements.define("morning-routine-card", MorningRoutineCard);
}
