// The Morning Routine dashboard card.
// The top half is plain logic with no browser in it, so Node can test it.
// The element that draws the card is at the bottom.

const PROBLEM_TEXT = {
  sensor_missing:
    "This phone's Next alarm sensor is turned off or missing. Turn it on in the Home Assistant Android app, under Settings, Companion app, Manage sensors.",
  sensor_stale:
    "The phone is reporting an alarm time that has already passed. This usually means the Next alarm sensor's Allow list is on. Turn the Allow list off in the Home Assistant Android app.",
  no_clock: "Choose a clock below. Nothing runs until one is chosen.",
};

const SETTINGS = ["brightness", "temperature", "heat_to", "cool_to"];
const isSet = (value) => value !== null && value !== undefined;
const isNumber = (value) => typeof value === "number" && Number.isFinite(value);

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

// A script, scene or automation runs. It can be a step once.
const runsOnce = (entry) => entry.actions.some((action) => action.action === "run");

// What the form's picker offers. A script, scene or automation can be a step once, so one that
// another step uses is left out. A light or thermostat can be a step any number of times.
export function formItems(view, editingId) {
  const usedByOthers = new Set(
    view.steps.filter((step) => step.action === "run" && step.id !== editingId).map((step) => step.item),
  );
  return view.items.filter((entry) => !(runsOnce(entry) && usedByOthers.has(entry.item)));
}

// ----- The form's state -----
// The form holds one plain object: { editing, item, action, values, checked, locked }.
// `values` maps a setting's key to the number held for it. `checked` maps an optional setting's
// key to whether it is ticked. `locked` means the item can't show what the step does, so only
// the step's time can change. Every change to the form goes through one of the functions below,
// and what is saved is worked out from the same state the form is drawn from.

// The item the form is on, with what it can do. Null when nothing is chosen or it isn't offered.
export function formEntry(view, state) {
  return formItems(view, state.editing).find((entry) => entry.item === state.item) || null;
}

export function actionOf(entry, action) {
  return (entry && entry.actions.find((choice) => choice.action === action)) || null;
}

function inside(setting, value) {
  const limits = setting.selector.number;
  return value >= limits.min && value <= limits.max;
}

function savedSettings(step) {
  return Object.fromEntries(SETTINGS.filter((key) => isSet(step[key])).map((key) => [key, step[key]]));
}

// Whether an item's description can draw a saved step as controls.
export function canShow(entry, step) {
  const action = actionOf(entry, step.action);
  if (!action) return false;
  const offered = new Set(action.settings.map((setting) => setting.key));
  if (SETTINGS.some((key) => isSet(step[key]) && !offered.has(key))) return false;
  return action.settings.every((setting) => {
    const value = step[setting.key];
    return isSet(value) ? inside(setting, value) : setting.optional;
  });
}

export function startForm(view, editingId) {
  if (editingId === null) return { editing: null, item: "", action: null, values: {}, checked: {}, locked: false };
  const step = view.steps.find((entry) => entry.id === editingId);
  const state = { editing: editingId, item: step.item, action: step.action, values: {}, checked: {}, locked: false };
  const entry = formEntry(view, state);
  if (!entry || !canShow(entry, step)) return { ...state, values: savedSettings(step), locked: true };
  for (const setting of actionOf(entry, step.action).settings) {
    const saved = step[setting.key];
    state.values[setting.key] = isSet(saved) ? saved : setting.start;
    if (setting.optional) state.checked[setting.key] = isSet(saved);
  }
  return state;
}

// The values and ticks for an action's settings. What is already held for a setting is kept.
function settingsState(settings, held) {
  const values = { ...held.values };
  const checked = { ...held.checked };
  for (const setting of settings) {
    const value = values[setting.key];
    if (!isNumber(value) || !inside(setting, value)) values[setting.key] = setting.start;
    if (setting.optional) checked[setting.key] = checked[setting.key] === true;
  }
  return { values, checked };
}

export function withItem(state, entry) {
  if (!entry) return { ...state, item: "", action: null, values: {}, checked: {} };
  const action = entry.actions[0];
  return { ...state, item: entry.item, action: action.action, ...settingsState(action.settings, { values: {}, checked: {} }) };
}

export function withAction(state, entry, action) {
  const chosen = actionOf(entry, action);
  return chosen ? { ...state, action, ...settingsState(chosen.settings, state) } : state;
}

// Ticking a setting whose box was left empty starts it over at its start value.
export function withChecked(state, setting, checked) {
  const value = state.values[setting.key];
  return {
    ...state,
    checked: { ...state.checked, [setting.key]: checked },
    values: { ...state.values, [setting.key]: checked && !isNumber(value) ? setting.start : value },
  };
}

// An emptied number box reports no value. It is held as null, and nothing is saved until it has a number.
export function withValue(state, key, value) {
  return { ...state, values: { ...state.values, [key]: isNumber(value) ? value : null } };
}

// The step to send: only the settings that are drawn, each exactly as held. Null when there is
// nothing to send yet.
export function formStep(state, entry) {
  if (state.locked) return { item: state.item, action: state.action, ...state.values };
  const action = actionOf(entry, state.action);
  if (!action || entry.item !== state.item) return null;
  const step = { item: state.item, action: state.action };
  for (const setting of action.settings) {
    if (setting.optional && !state.checked[setting.key]) continue;
    const value = state.values[setting.key];
    if (!isNumber(value)) return null;
    step[setting.key] = value;
  }
  return step;
}

// A new view arrived while the form is open. Returns the state to draw and a note for the
// person: "choice_gone", "item_changed", or null when nothing they can see changed.
export function refreshed(state, before, view) {
  if (state.locked) {
    const step = view.steps.find((entry) => entry.id === state.editing);
    return { state: step ? { ...state, action: step.action, values: savedSettings(step) } : state, note: null };
  }
  if (!state.item) return { state, note: null };
  const entry = formEntry(view, state);
  if (!entry) return { state: withItem(state, null), note: "choice_gone" };
  const action = actionOf(entry, state.action);
  if (!action) return { state: withItem(state, entry), note: "item_changed" };

  const old = actionOf(formEntry(before, state), state.action);
  const oldSettings = old ? old.settings : [];
  const drawn = (setting) => !setting.optional || state.checked[setting.key] === true;
  const shape = (settings) => settings.map((setting) => `${setting.key}:${setting.optional}`).join();
  let changed = shape(oldSettings) !== shape(action.settings);
  const values = { ...state.values };
  const checked = { ...state.checked };
  for (const setting of oldSettings) {
    if (!action.settings.some((kept) => kept.key === setting.key)) {
      delete values[setting.key];
      delete checked[setting.key];
    }
  }
  for (const setting of action.settings) {
    const was = oldSettings.find((kept) => kept.key === setting.key);
    const value = values[setting.key];
    if (!was) {
      values[setting.key] = setting.start;
      if (setting.optional) checked[setting.key] = false;
      continue;
    }
    if (isNumber(value) && !inside(setting, value)) {
      const limits = setting.selector.number;
      values[setting.key] = Math.min(Math.max(value, limits.min), limits.max);
      if (drawn(setting)) changed = true;
    }
    if (drawn(setting) && JSON.stringify(was.selector) !== JSON.stringify(setting.selector)) changed = true;
  }
  if (!changed && JSON.stringify(values) === JSON.stringify(state.values)) return { state, note: null };
  return { state: { ...state, values, checked }, note: changed ? "item_changed" : null };
}

function wireStep(step) {
  const wire = {
    id: step.id,
    item: step.item,
    offset_minutes: step.offset_minutes,
    enabled: step.enabled,
    action: step.action,
  };
  for (const name of SETTINGS) {
    if (isSet(step[name])) wire[name] = step[name];
  }
  return wire;
}

function wireSteps(view) {
  return view.steps.map(wireStep);
}

export function withToggled(view, id, enabled) {
  return wireSteps(view).map((step) => (step.id === id ? { ...step, enabled } : step));
}

// `step` is what the form holds: item, offset_minutes, action and any settings.
export function withSaved(view, editingId, step) {
  const steps = wireSteps(view);
  if (editingId === null) return [...steps, { ...step, enabled: true }];
  return steps.map((old) => {
    if (old.id !== editingId) return old;
    // A step that now does something else is a new step. The server gives it a new id,
    // so having run under the old one this morning doesn't hold it back.
    const same = old.item === step.item && old.action === step.action;
    return same ? { id: old.id, ...step, enabled: old.enabled } : { ...step, enabled: old.enabled };
  });
}

export function withRemoved(view, id) {
  return wireSteps(view).filter((step) => step.id !== id);
}

export function problemText(code) {
  return PROBLEM_TEXT[code] ?? null;
}


// ---------------------------------------------------------------------------
// The element. Everything below needs a browser.
// ---------------------------------------------------------------------------

if (globalThis.customElements) {
  const RETRY_MS = 10000;
  const SUBTITLE = "Runs around each alarm from the clock below, only when this phone is home";
  const TEXT_NO_ROUTINE = "Choose a routine in this card's settings.";
  const TEXT_UNAVAILABLE = "This routine isn't available. It may have been removed.";
  const TEXT_STEP_GONE = 'No longer available. It was deleted or lost the "morning routine" label.';
  const TEXT_DEVICE_GONE = "No longer available. It was deleted.";
  const TEXT_NOTHING_TO_ADD =
    'There is nothing to add yet. A step can be a light, a thermostat, or a script, scene or automation that an admin gave the "morning routine" label.';
  const TEXT_LABEL_NOTE =
    'Scripts, scenes and automations appear here once an admin gives them the "morning routine" label.';
  const FIELD_TEXT = {
    brightness: { label: "Brightness", hint: "as it was", unit: () => "%" },
    temperature: { label: "Temperature", hint: "last setting", unit: (view) => view.temperature_unit || "" },
    heat_to: { label: "Heat to", hint: "", unit: (view) => view.temperature_unit || "" },
    cool_to: { label: "Cool to", hint: "", unit: (view) => view.temperature_unit || "" },
  };
  const TEXT_NOT_SAVED = "That change couldn't be saved.";
  const TEXT_CHOICE_GONE = "That choice is no longer available. Choose again.";

  const STYLE = `
    :host { display: block; }
    ha-card { display: block; color: var(--primary-text-color); font-size: 14px; line-height: 1.35; overflow: hidden; }
    .section { padding: 14px 16px; border-bottom: 1px solid var(--divider-color); }
    .section:last-child { border-bottom: 0; }
    .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .title { font-size: 17px; font-weight: 500; overflow-wrap: anywhere; }
    .note { color: var(--secondary-text-color); font-size: 13px; margin: 6px 0 0; overflow-wrap: anywhere; }
    .only { margin: 0; padding: 16px; color: var(--secondary-text-color); }
    .step { display: grid; grid-template-columns: 86px 20px minmax(0, 1fr) 36px; column-gap: 8px; align-items: start; min-height: 50px; }
    .step.last { min-height: 30px; }
    .when { color: var(--secondary-text-color); font-size: 12.5px; text-align: right; padding-top: 1px; }
    .line { position: relative; align-self: stretch; }
    .line::before { content: ""; position: absolute; left: 9px; top: 0; bottom: 0; width: 2px; background: var(--divider-color); }
    .step.first .line::before { top: 8px; }
    .step.last .line::before { bottom: auto; height: 8px; }
    .step.first.last .line::before { display: none; }
    .dot { position: absolute; left: 4px; top: 3px; width: 12px; height: 12px; border-radius: 50%; box-sizing: border-box; background: var(--card-background-color); border: 2px solid var(--primary-color); }
    .dot.alarm { left: 1px; top: 0; width: 18px; height: 18px; background: var(--primary-color); }
    .off .dot { border-color: var(--secondary-text-color); }
    .off .name, .gone .name { color: var(--secondary-text-color); }
    .name { font: inherit; font-size: 14.5px; color: inherit; background: none; border: 0; padding: 0; margin: 0; text-align: left; cursor: pointer; overflow-wrap: anywhere; }
    .alarm-name { font-size: 14.5px; font-weight: 500; }
    .step .note { margin: 2px 0 10px; font-size: 12.5px; }
    .text-button { font: inherit; font-weight: 500; color: var(--primary-color); background: none; border: 0; padding: 8px; margin: 0; cursor: pointer; border-radius: 4px; }
    .text-button.quiet { color: var(--secondary-text-color); }
    .text-button:disabled { opacity: 0.5; cursor: default; }
    .add { display: block; margin: 2px auto 0; }
    .label { display: block; color: var(--secondary-text-color); font-size: 12.5px; margin: 12px 0 6px; }
    select, input.minutes, input.search { font: inherit; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-bottom-color: var(--secondary-text-color); border-radius: 4px 4px 0 0; padding: 9px 10px; box-sizing: border-box; min-width: 0; }
    select.wide { width: 100%; }
    input.minutes { width: 64px; }
    input.search { width: 100%; margin-bottom: 6px; }
    .setting-row { display: flex; align-items: center; gap: 8px; }
    select:disabled { opacity: 0.5; }
    input.switch { appearance: none; -webkit-appearance: none; flex: none; position: relative; width: 36px; height: 20px; margin: 0; border-radius: 10px; cursor: pointer; background: color-mix(in srgb, var(--secondary-text-color) 55%, transparent); transition: background 0.15s; }
    input.switch::before { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: var(--card-background-color); box-shadow: 0 0 2px rgba(0, 0, 0, 0.5); transition: left 0.15s; }
    input.switch:checked { background: var(--primary-color); }
    input.switch:checked::before { left: 18px; }
    input.switch:disabled { opacity: 0.5; cursor: default; }
    :focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
    dialog { color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 12px; padding: 16px; width: min(340px, calc(100vw - 48px)); box-sizing: border-box; font-size: 14px; line-height: 1.35; }
    dialog::backdrop { background: rgba(0, 0, 0, 0.5); }
    dialog form { margin: 0; }
    .when-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .when-row select { flex: 1 1 130px; }
    .buttons { display: flex; align-items: center; justify-content: flex-end; gap: 4px; margin-top: 16px; }
    .buttons .spacer { flex: 1; }
  `;

  function h(tag, props = {}, ...children) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (value === false || value === null || value === undefined) continue;
      if (key === "class") element.className = value;
      else if (key.startsWith("on")) element.addEventListener(key.slice(2), value);
      else if (key.includes("-") || key === "role" || key === "for") element.setAttribute(key, value);
      else element[key] = value;
    }
    for (const child of children.flat()) {
      if (child !== false && child !== null && child !== undefined) element.append(child);
    }
    return element;
  }

  function quietly(unsubscribe) {
    if (!unsubscribe) return;
    try {
      Promise.resolve(unsubscribe()).catch(() => {});
    } catch {
      // The server had already dropped it.
    }
  }

  class MorningRoutineCard extends HTMLElement {
    static getConfigForm() {
      return {
        schema: [{ name: "routine", required: true, selector: { config_entry: { integration: "morning_routine" } } }],
      };
    }

    static getStubConfig() {
      return { routine: "" };
    }

    constructor() {
      super();
      this._routineId = "";
      this._hass = null;
      this._connection = null;
      this._view = null;
      this._title = null;
      this._unavailable = false;
      this._unsubscribe = null;
      this._pending = null;
      this._generation = 0;
      this._retry = null;
      this._busy = false;
      this._refused = null;
      this._form = null;
      this._onReady = () => {
        // The connection came back. The old subscription is gone with the old connection.
        this._generation += 1;
        this._unsubscribe = null;
        this._clearRetry();
        this._subscribe();
      };
      this.attachShadow({ mode: "open" });
      this._card = h("ha-card");
      this._dialog = h("dialog", {
        onclose: () => {
          this._form = null;
        },
      });
      this.shadowRoot.append(h("style", {}, STYLE), this._card, this._dialog);
    }

    setConfig(config) {
      const routineId = (config && config.routine) || "";
      if (routineId !== this._routineId) {
        this._stop();
        this._routineId = routineId;
        this._view = null;
        this._title = null;
        this._unavailable = false;
        this._refused = null;
        this._closeForm();
      }
      this._render();
      this._subscribe();
    }

    set hass(hass) {
      this._hass = hass;
      if (this.isConnected && hass.connection !== this._connection) {
        this._forgetConnection();
        this._connection = hass.connection;
        if (this._connection.addEventListener) this._connection.addEventListener("ready", this._onReady);
      }
      this._subscribe();
    }

    getCardSize() {
      return 4 + (this._view ? this._view.steps.length : 0);
    }

    connectedCallback() {
      this._render();
      if (this._hass) this.hass = this._hass;
    }

    disconnectedCallback() {
      this._stop();
      this._forgetConnection();
      this._closeForm();
    }

    _forgetConnection() {
      if (this._connection && this._connection.removeEventListener) {
        this._connection.removeEventListener("ready", this._onReady);
      }
      this._connection = null;
    }

    _clearRetry() {
      if (this._retry !== null) {
        clearTimeout(this._retry);
        this._retry = null;
      }
    }

    _stop() {
      this._generation += 1;
      this._clearRetry();
      quietly(this._unsubscribe);
      this._unsubscribe = null;
    }

    async _subscribe() {
      const generation = this._generation;
      // A call from before the last drop or change may never be answered, so only a call
      // made for the current generation counts as waiting.
      if (this._pending === generation || this._unsubscribe || this._retry !== null) return;
      if (!this.isConnected || !this._hass || !this._routineId) return;
      // Nothing can be sent while the connection is down. Its "ready" event subscribes again.
      if (this._hass.connection.connected === false) return;
      this._pending = generation;
      let unsubscribe = null;
      let failed = false;
      try {
        unsubscribe = await this._hass.connection.subscribeMessage(
          (event) => {
            if (generation === this._generation) this._onEvent(event);
          },
          { type: "morning_routine/subscribe", entry_id: this._routineId },
          { resubscribe: false },
        );
      } catch {
        failed = true;
      }
      if (this._pending === generation) this._pending = null;
      if (generation !== this._generation) {
        // Something changed while waiting: the page was left, or the routine was swapped.
        quietly(unsubscribe);
        this._subscribe();
        return;
      }
      if (failed) {
        this._showUnavailable();
        return;
      }
      this._unsubscribe = unsubscribe;
    }

    _onEvent(event) {
      if (event && event.unavailable) {
        this._showUnavailable();
        return;
      }
      if (!event || !event.view) return;
      this._view = event.view;
      this._title = event.view.title;
      this._unavailable = false;
      this._refused = null;
      this._render();
      this._refreshForm();
    }

    _showUnavailable() {
      this._generation += 1;
      quietly(this._unsubscribe);
      this._unsubscribe = null;
      this._view = null;
      this._unavailable = true;
      this._refused = null;
      this._closeForm();
      this._render();
      this._clearRetry();
      this._retry = setTimeout(() => {
        this._retry = null;
        this._subscribe();
      }, RETRY_MS);
    }

    async _send(message, onRefused) {
      if (this._busy || !this._view) return false;
      this._busy = true;
      this._refused = null;
      this._render();
      let saved = true;
      try {
        await this._hass.connection.sendMessagePromise({ ...message, entry_id: this._view.entry_id });
      } catch (err) {
        saved = false;
        const text = (err && err.message) || TEXT_NOT_SAVED;
        if (onRefused) onRefused(text);
        else this._refused = text;
      }
      this._busy = false;
      this._render();
      return saved;
    }

    _switch(key, label, checked, change) {
      return h("input", {
        type: "checkbox",
        role: "switch",
        class: "switch",
        "aria-label": label,
        "data-key": key,
        checked,
        disabled: this._busy,
        onclick: (event) => {
          // The switch moves when the server's next view says so, not on the tap.
          event.preventDefault();
          change(!checked);
        },
      });
    }

    _render() {
      const active = this.shadowRoot.activeElement;
      const focusedKey = active && this._card.contains(active) ? active.getAttribute("data-key") : null;
      this._card.replaceChildren(...this._content());
      if (focusedKey) {
        for (const control of this._card.querySelectorAll("[data-key]")) {
          if (control.getAttribute("data-key") === focusedKey) control.focus();
        }
      }
      this._syncFormButtons();
    }

    _content() {
      if (!this._routineId) return [h("p", { class: "only" }, TEXT_NO_ROUTINE)];
      if (this._unavailable) {
        return [
          h(
            "div",
            { class: "section" },
            this._title && h("div", { class: "title" }, this._title),
            h("p", { class: "note" }, TEXT_UNAVAILABLE),
          ),
        ];
      }
      const view = this._view;
      if (!view) return [];
      return [this._headerSection(view), this._timelineSection(view), this._settingsSection(view)];
    }

    _headerSection(view) {
      return h(
        "div",
        { class: "section" },
        h(
          "div",
          { class: "row" },
          h("div", { class: "title" }, view.title),
          this._switch("routine", "Routine", view.is_on, (on) => this._send({ type: "morning_routine/update", is_on: on })),
        ),
        h("p", { class: "note" }, SUBTITLE),
        view.problems.map((code) => problemText(code)).filter(Boolean).map((text) => h("p", { class: "note" }, text)),
      );
    }

    _timelineSection(view) {
      const rows = timelineRows(view.steps);
      const canAdd = formItems(view, null).length > 0;
      return h(
        "div",
        { class: "section" },
        rows.map((row, index) => {
          const edge = `${index === 0 ? " first" : ""}${index === rows.length - 1 ? " last" : ""}`;
          return row.type === "alarm" ? this._alarmRow(edge) : this._stepRow(view, row.step, edge);
        }),
        this._refused && h("p", { class: "note", role: "status" }, this._refused),
        canAdd &&
          h(
            "button",
            { type: "button", class: "text-button add", "data-key": "add", onclick: () => this._openForm(null) },
            "+ Add a step",
          ),
        !canAdd && h("p", { class: "note" }, TEXT_NOTHING_TO_ADD),
      );
    }

    _alarmRow(edge) {
      return h(
        "div",
        { class: `step${edge}` },
        h("div", { class: "when" }),
        h("div", { class: "line" }, h("div", { class: "dot alarm" })),
        h("div", { class: "alarm-name" }, "Alarm"),
        h("div"),
      );
    }

    _stepRow(view, step, edge) {
      const state = !step.available ? " gone" : step.enabled ? "" : " off";
      const detail = step.detail;
      return h(
        "div",
        { class: `step${edge}${state}` },
        h("div", { class: "when" }, offsetLabel(step.offset_minutes)),
        h("div", { class: "line" }, h("div", { class: "dot" })),
        h(
          "div",
          {},
          h(
            "button",
            {
              type: "button",
              class: "name",
              "data-key": `name:${step.id}`,
              "aria-label": `Edit step: ${step.name}`,
              onclick: () => this._openForm(step.id),
            },
            step.name,
          ),
          detail && h("p", { class: "note" }, detail),
          !step.available && h("p", { class: "note" }, step.action === "run" ? TEXT_STEP_GONE : TEXT_DEVICE_GONE),
        ),
        step.available
          ? this._switch(`step:${step.id}`, detail ? `${step.name}: ${detail}` : step.name, step.enabled, (enabled) =>
              this._send({ type: "morning_routine/set_steps", steps: withToggled(this._view, step.id, enabled) }),
            )
          : h("div"),
      );
    }

    _settingsSection(view) {
      const options = view.clock_options.map((option) =>
        h("option", { value: option.package, selected: option.package === view.clock }, option.name),
      );
      if (view.clock === null) {
        options.unshift(h("option", { value: "", selected: true, disabled: true }, "Choose a clock"));
      }
      return h(
        "div",
        { class: "section" },
        h(
          "div",
          { class: "row" },
          h("div", {}, "Skip next alarm"),
          this._switch("skip", "Skip next alarm", view.skip_next, (on) =>
            this._send({ type: "morning_routine/update", skip_next: on }),
          ),
        ),
        h("label", { class: "label", for: "clock" }, "Clock to watch"),
        h(
          "select",
          {
            id: "clock",
            class: "wide",
            "data-key": "clock",
            disabled: this._busy,
            onchange: (event) => {
              const clock = event.target.value;
              if (clock) this._send({ type: "morning_routine/update", clock });
            },
          },
          options,
        ),
      );
    }

    // ----- The step form -----

    _openForm(editingId) {
      const view = this._view;
      if (!view || this._busy) return;
      const step = editingId === null ? null : view.steps.find((entry) => entry.id === editingId);
      if (editingId !== null && !step) return;
      const { minutes, direction } = step ? splitOffset(step.offset_minutes) : { minutes: 30, direction: "before" };

      const search = h("input", {
        class: "search",
        type: "search",
        autocomplete: "off",
        placeholder: "Search",
        "aria-label": "Search what should happen",
        // Enter in a text box would submit the form, and searching must never save a step.
        onkeydown: (event) => {
          if (event.key === "Enter") event.preventDefault();
        },
        oninput: () => this._fillFormItems(this._form.item.value),
      });
      const item = h("select", {
        id: "form-item",
        class: "wide",
        // Without this the dialog opens on the search box, and a phone raises its keyboard.
        autofocus: true,
        onchange: () => {
          this._fillFormSettings();
          this._syncFormButtons();
        },
      });
      const labelNote = h("p", { class: "note" });
      const settings = h("div");
      const minutesBox = h("input", {
        id: "form-minutes",
        class: "minutes",
        type: "text",
        inputMode: "numeric",
        autocomplete: "off",
        value: String(minutes),
        "aria-describedby": "form-error",
      });
      const directionBox = h(
        "select",
        { "aria-label": "Before or after the alarm" },
        h("option", { value: "before", selected: direction === "before" }, "before the alarm"),
        h("option", { value: "after", selected: direction === "after" }, "after the alarm"),
      );
      const error = h("p", { id: "form-error", class: "note", role: "status" });
      const save = h("button", { type: "submit", class: "text-button" }, "Save");
      const remove =
        step && h("button", { type: "button", class: "text-button quiet", onclick: () => this._removeFromForm() }, "Remove step");

      this._form = {
        editing: editingId,
        search,
        item,
        labelNote,
        settings,
        settingsFor: null,
        actionBox: null,
        boxes: {},
        minutesBox,
        directionBox,
        error,
        save,
        remove,
      };
      // A new step starts on "Choose one", so nothing is added by a stray tap on Save.
      this._fillFormItems(step ? step.item : "");
      this._fillFormSettings();
      this._dialog.replaceChildren(
        h(
          "form",
          {
            method: "dialog",
            onsubmit: (event) => {
              event.preventDefault();
              this._saveForm();
            },
          },
          h("div", { class: "title" }, step ? "Edit step" : "Add a step"),
          h("label", { class: "label", for: "form-item" }, "What should happen"),
          search,
          item,
          labelNote,
          settings,
          h("label", { class: "label", for: "form-minutes" }, "When"),
          h("div", { class: "when-row" }, minutesBox, h("span", {}, "minutes"), directionBox),
          error,
          h(
            "div",
            { class: "buttons" },
            remove,
            h("span", { class: "spacer" }),
            h("button", { type: "button", class: "text-button", onclick: () => this._closeForm() }, "Cancel"),
            save,
          ),
        ),
      );
      this._syncFormButtons();
      this._dialog.showModal();
    }

    _fillFormItems(selected) {
      const form = this._form;
      const items = formItems(this._view, form.editing);
      const keep = chosenItem(items, selected);
      const option = (entry) => h("option", { value: entry.item, selected: entry.item === keep }, entry.name);
      const options = itemGroups(searchItems(items, form.search.value, keep)).map((group) =>
        group.title ? h("optgroup", { label: group.title }, group.items.map(option)) : group.items.map(option),
      );
      if (keep === "") options.unshift(h("option", { value: "", selected: true, disabled: true }, "Choose one"));
      form.item.replaceChildren(...options.flat());
      form.labelNote.textContent = items.some((entry) => entry.type === "run") ? "" : TEXT_LABEL_NOTE;
      return keep;
    }

    // The item the picker is on, with what it can do. Null when nothing is chosen.
    _formEntry() {
      const form = this._form;
      return formItems(this._view, form.editing).find((entry) => entry.item === form.item.value) || null;
    }

    _formAction(entry) {
      const form = this._form;
      const choices = actionChoices(entry);
      if (!choices.length) return null;
      if (form.actionBox && choices.some((choice) => choice.action === form.actionBox.value)) {
        return form.actionBox.value;
      }
      return choices[0].action;
    }

    // Draws the action and its settings for the chosen item. Only redrawn when the item or the
    // action changes, so what was typed survives a new view from the server.
    _fillFormSettings() {
      const form = this._form;
      const view = this._view;
      const entry = this._formEntry();
      const own = form.editing === null ? null : view.steps.find((step) => step.id === form.editing) || null;
      const choices = actionChoices(entry);
      const startsOnOwn = own && entry && own.item === entry.item && form.settingsFor === null;
      const action =
        startsOnOwn && choices.some((choice) => choice.action === own.action) ? own.action : this._formAction(entry);
      const key = entry ? `${entry.item}|${action}` : "";
      if (key === form.settingsFor) return;
      form.settingsFor = key;
      form.actionBox = null;
      form.boxes = {};
      if (!choices.length) {
        form.settings.replaceChildren();
        return;
      }
      form.actionBox = h(
        "select",
        {
          id: "form-action",
          class: "wide",
          onchange: () => this._fillFormSettings(),
        },
        choices.map((choice) => h("option", { value: choice.action, selected: choice.action === action }, choice.text)),
      );
      const rows = [h("label", { class: "label", for: "form-action" }, "What to do"), form.actionBox];
      const prefill = own && own.item === entry.item && own.action === action ? own : {};
      for (const name of settingFields(entry, action)) {
        const text = FIELD_TEXT[name];
        const value = prefill[name];
        const box = h("input", {
          id: `form-${name}`,
          class: "minutes",
          type: "text",
          inputMode: "decimal",
          autocomplete: "off",
          placeholder: text.hint,
          value: value === null || value === undefined ? "" : String(value),
          "aria-describedby": "form-error",
        });
        form.boxes[name] = box;
        rows.push(
          h("label", { class: "label", for: `form-${name}` }, text.label),
          h("div", { class: "setting-row" }, box, h("span", {}, text.unit(view))),
        );
      }
      form.settings.replaceChildren(...rows);
    }

    _refreshForm() {
      const form = this._form;
      if (!form) return;
      if (form.editing !== null && !this._view.steps.some((step) => step.id === form.editing)) {
        // Someone else removed the step being edited.
        this._closeForm();
        return;
      }
      const before = form.item.value;
      if (this._fillFormItems(before) !== before) form.error.textContent = TEXT_CHOICE_GONE;
      this._fillFormSettings();
      this._syncFormButtons();
    }

    _syncFormButtons() {
      const form = this._form;
      if (!form) return;
      form.save.disabled = this._busy || !form.item.value;
      if (form.remove) form.remove.disabled = this._busy;
    }

    _closeForm() {
      if (this._dialog.open) this._dialog.close();
      this._form = null;
    }

    async _saveForm() {
      const form = this._form;
      if (!form || this._busy || !form.item.value) return;
      const direction = form.directionBox.value;
      const problem = offsetError(form.minutesBox.value, direction, this._view);
      form.error.textContent = problem || "";
      if (problem) return;
      const entry = this._formEntry();
      const own = form.editing === null ? null : this._view.steps.find((step) => step.id === form.editing) || null;
      let what;
      if (entry && entry.type === "run") {
        what = { action: "run" };
      } else if (actionChoices(entry).length) {
        const action = this._formAction(entry);
        const fields = Object.fromEntries(Object.entries(form.boxes).map(([name, box]) => [name, box.value]));
        const settingsProblem = settingsError(entry, action, fields);
        form.error.textContent = settingsProblem || "";
        if (settingsProblem) return;
        what = { action, ...settingsOf(entry, action, fields) };
      } else if (own && own.item === form.item.value) {
        // The step's own device is gone, so only its time can change. What it does stays as it was.
        what = { action: own.action };
        for (const name of ["brightness", "temperature", "heat_to", "cool_to"]) {
          if (own[name] !== null && own[name] !== undefined) what[name] = own[name];
        }
      } else {
        return;
      }
      const steps = withSaved(this._view, form.editing, {
        item: form.item.value,
        offset_minutes: joinOffset(Number(form.minutesBox.value.trim()), direction),
        ...what,
      });
      const saved = await this._send({ type: "morning_routine/set_steps", steps }, (text) => {
        form.error.textContent = text;
      });
      if (saved && this._form === form) this._closeForm();
    }

    async _removeFromForm() {
      const form = this._form;
      if (!form || this._busy) return;
      form.error.textContent = "";
      const steps = withRemoved(this._view, form.editing);
      const saved = await this._send({ type: "morning_routine/set_steps", steps }, (text) => {
        form.error.textContent = text;
      });
      if (saved && this._form === form) this._closeForm();
    }
  }

  if (!customElements.get("morning-routine-card")) {
    customElements.define("morning-routine-card", MorningRoutineCard);
  }
  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "morning-routine-card")) {
    window.customCards.push({
      type: "morning-routine-card",
      name: "Morning Routine",
      description: "Steps that run around a phone's alarm.",
    });
  }
}
