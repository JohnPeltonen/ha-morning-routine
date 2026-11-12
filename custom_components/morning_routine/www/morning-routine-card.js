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

// Which item the form's picker shows. `selected` is null for a form that was just opened.
// A choice that is no longer offered becomes no choice, never a different item.
export function chosenItem(items, selected) {
  if (selected === null) return items.length ? items[0].item : "";
  return items.some((entry) => entry.item === selected) ? selected : "";
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


// ---------------------------------------------------------------------------
// The element. Everything below needs a browser.
// ---------------------------------------------------------------------------

if (globalThis.customElements) {
  const RETRY_MS = 10000;
  const SUBTITLE = "Runs around each alarm from the clock below, only when this phone is home";
  const TEXT_NO_ROUTINE = "Choose a routine in this card's settings.";
  const TEXT_UNAVAILABLE = "This routine isn't available. It may have been removed.";
  const TEXT_STEP_GONE = 'No longer available. It was deleted or lost the "morning routine" label.';
  const TEXT_NOTHING_TO_ADD =
    'Nothing else has the "morning routine" label. An admin can add the label to a script, scene or automation.';
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
    select, input.minutes { font: inherit; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-bottom-color: var(--secondary-text-color); border-radius: 4px 4px 0 0; padding: 9px 10px; box-sizing: border-box; min-width: 0; }
    select.wide { width: 100%; }
    input.minutes { width: 64px; }
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
        !canAdd && !view.problems.includes("no_label") && h("p", { class: "note" }, TEXT_NOTHING_TO_ADD),
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
              "data-key": `name:${step.item}`,
              "aria-label": `Edit step: ${step.name}`,
              onclick: () => this._openForm(step.item),
            },
            step.name,
          ),
          !step.available && h("p", { class: "note" }, TEXT_STEP_GONE),
        ),
        step.available
          ? this._switch(`step:${step.item}`, step.name, step.enabled, (enabled) =>
              this._send({ type: "morning_routine/set_steps", steps: withToggled(this._view, step.item, enabled) }),
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

    _openForm(editingItem) {
      const view = this._view;
      if (!view || this._busy) return;
      const step = editingItem === null ? null : view.steps.find((entry) => entry.item === editingItem);
      if (editingItem !== null && !step) return;
      const { minutes, direction } = step ? splitOffset(step.offset_minutes) : { minutes: 30, direction: "before" };

      const item = h("select", { id: "form-item", class: "wide", onchange: () => this._syncFormButtons() });
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

      this._form = { editing: editingItem, item, minutesBox, directionBox, error, save, remove };
      this._fillFormItems(step ? step.item : null);
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
          item,
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
      const options = items.map((entry) => h("option", { value: entry.item, selected: entry.item === keep }, entry.name));
      if (keep === "") options.unshift(h("option", { value: "", selected: true, disabled: true }, "Choose one"));
      form.item.replaceChildren(...options);
      return keep;
    }

    _refreshForm() {
      const form = this._form;
      if (!form) return;
      if (form.editing !== null && !this._view.steps.some((step) => step.item === form.editing)) {
        // Someone else removed the step being edited.
        this._closeForm();
        return;
      }
      const before = form.item.value;
      if (this._fillFormItems(before) !== before) form.error.textContent = TEXT_CHOICE_GONE;
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
      const steps = withSaved(this._view, form.editing, {
        item: form.item.value,
        offset_minutes: joinOffset(Number(form.minutesBox.value.trim()), direction),
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
