// The card's face and its form, with stand-ins for Home Assistant's controls.
// Each test imports its own copy of the card, so each can decide which controls exist.
import assert from "node:assert/strict";
import { mock, test } from "node:test";

mock.timers.enable({ apis: ["setTimeout"] });

const CARD_FILE = "../../custom_components/morning_routine/www/morning-routine-card.js";
const CONTROL_TAGS = ["ha-selector", "ha-switch", "ha-checkbox", "ha-formfield", "ha-button"];
const SELECTOR_TAGS = ["ha-selector-entity", "ha-selector-number", "ha-selector-select", "ha-selector-button_toggle"];

class FakeElement {
  constructor(tag) {
    this.localName = tag;
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.parent = null;
    this.open = false;
    this.textContent = "";
  }
  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  setAttribute(key, value) {
    this.attributes[key] = String(value);
  }
  getAttribute(key) {
    return this.attributes[key] ?? null;
  }
  append(...children) {
    for (const child of children) {
      if (child instanceof FakeElement) child.parent = this;
      this.children.push(child);
    }
  }
  replaceChildren(...children) {
    this.children = [];
    this.append(...children);
  }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this);
    this.parent = null;
  }
  *all() {
    for (const child of this.children) {
      if (!(child instanceof FakeElement)) continue;
      yield child;
      yield* child.all();
    }
  }
  // Enough of a selector for the card: a tag name, or [attribute].
  querySelectorAll(selector) {
    const attribute = selector.match(/^\[(.+)\]$/);
    return [...this.all()].filter((element) =>
      attribute ? element.getAttribute(attribute[1]) !== null : element.localName === selector,
    );
  }
  contains(element) {
    return [...this.all()].includes(element);
  }
  focus() {}
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
    this.fire("close");
  }
  fire(type, detail) {
    const event = { type, detail, target: this, currentTarget: this, stopPropagation() {}, preventDefault() {} };
    for (const listener of this.listeners[type] || []) listener(event);
  }
  get text() {
    return this.textContent + this.children.map((child) => (child instanceof FakeElement ? child.text : child)).join("");
  }
}

class Registry {
  constructor() {
    this.classes = new Map();
    this.waiting = new Map();
  }
  get(tag) {
    return this.classes.get(tag);
  }
  define(tag, element = class {}) {
    this.classes.set(tag, element);
    for (const resolve of this.waiting.get(tag) || []) resolve();
    this.waiting.delete(tag);
  }
  whenDefined(tag) {
    if (this.classes.has(tag)) return Promise.resolve();
    return new Promise((resolve) => this.waiting.set(tag, [...(this.waiting.get(tag) || []), resolve]));
  }
}

globalThis.HTMLElement = class {
  constructor() {
    this.isConnected = false;
  }
  attachShadow() {
    this.shadowRoot = new FakeElement("shadow-root");
    this.shadowRoot.activeElement = null;
    return this.shadowRoot;
  }
};
globalThis.document = { createElement: (tag) => new FakeElement(tag) };
globalThis.window = globalThis;

let copies = 0;
// A fresh copy of the card in a fresh registry. `tags` are the controls Home Assistant has defined.
async function freshCard(tags = []) {
  const registry = new Registry();
  for (const tag of tags) registry.define(tag);
  globalThis.customElements = registry;
  delete globalThis.loadCardHelpers;
  copies += 1;
  await import(`${CARD_FILE}?copy=${copies}`);
  return registry;
}
const ALL_CONTROLS = [...CONTROL_TAGS, ...SELECTOR_TAGS];

const slider = (min, max, unit) => ({ number: { min, max, step: 1, mode: "slider", unit_of_measurement: unit } });
const BRIGHTNESS = { key: "brightness", name: "Brightness", optional: true, hint: "as it was", start: 100, selector: slider(1, 100, "%") };
const TURN_OFF = { action: "turn_off", name: "Turn off", settings: [] };
const LAMP = { item: "light.lamp", name: "Lamp", actions: [{ action: "turn_on", name: "Turn on", settings: [BRIGHTNESS] }, TURN_OFF] };
const PLAIN_LAMP = { item: "light.lamp", name: "Lamp", actions: [{ action: "turn_on", name: "Turn on", settings: [] }, TURN_OFF] };
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
const savedStep = (extra) => ({
  enabled: true,
  available: true,
  brightness: null,
  temperature: null,
  heat_to: null,
  cool_to: null,
  detail: "",
  ...extra,
});
const HALL_STEP = savedStep({
  id: "h1",
  item: "climate.hall",
  name: "Hall",
  offset_minutes: -20,
  action: "set_temperature",
  heat_to: 68.3,
  cool_to: 74,
  detail: "Heat to 68.3°F, cool to 74°F",
});
const viewOf = (extra = {}) => ({
  entry_id: "demo",
  title: "Test routine",
  is_on: true,
  skip_next: false,
  clock: "com.example.clock",
  clock_options: [{ package: "com.example.clock", name: "Example Clock" }],
  steps: [],
  items: [LAMP, HALL],
  problems: [],
  min_offset_minutes: -720,
  max_offset_minutes: 60,
  ...extra,
});

class Connection {
  constructor(view) {
    this.connected = true;
    this.view = view;
    this.sent = [];
    this.refusal = null;
    this.push = null;
  }
  addEventListener() {}
  removeEventListener() {}
  async sendMessagePromise(message) {
    this.sent.push(message);
    if (this.refusal) throw { message: this.refusal };
    return null;
  }
  async subscribeMessage(callback) {
    this.push = (view) => callback({ view });
    setImmediate(() => callback({ view: this.view }));
    return async () => {};
  }
}

const settle = () => new Promise((resolve) => setImmediate(() => setImmediate(resolve)));

async function mount(registry, view = viewOf()) {
  const connection = new Connection(view);
  const Card = registry.get("morning-routine-card");
  const card = new Card();
  card.setConfig({ routine: "demo" });
  card.isConnected = true;
  card.connectedCallback();
  card.hass = { connection };
  await settle();
  await settle();
  return { card, connection };
}

const inCard = (card, test_) => [...card.shadowRoot.all()].filter(test_);
const byKey = (card, key) => inCard(card, (element) => element.getAttribute("data-key") === key)[0];
const dialogOf = (card) => inCard(card, (element) => element.localName === "dialog")[0];
const inForm = (card, test_) => [...dialogOf(card).all()].filter(test_);
const selectorWith = (card, type) => inForm(card, (element) => element.localName === "ha-selector" && element.selector[type])[0];
const settingSlider = (card, key) => inForm(card, (element) => element.getAttribute("data-setting") === key)[0];
const button = (card, words) => inForm(card, (element) => element.localName === "ha-button" && element.text === words)[0];

async function openForm(card, key = "add") {
  byKey(card, key).fire("click");
  await settle();
}
const choose = (card, item) => selectorWith(card, "entity").fire("value-changed", { value: item });
function tick(card, on = true) {
  const box = inForm(card, (element) => element.localName === "ha-checkbox")[0];
  box.checked = on;
  box.fire("change");
}
async function save(card) {
  button(card, "Save").fire("click");
  await settle();
}

// ----- The card's face -----

// Review Focus 1.
test("with no Home Assistant controls the card draws its own switches and dropdown, and the routine switch sends the change", async () => {
  const { card, connection } = await mount(await freshCard());

  const routine = byKey(card, "routine");
  assert.equal(routine.localName, "input");
  assert.equal(byKey(card, "skip").localName, "input");
  assert.equal(byKey(card, "clock").localName, "select");
  routine.fire("click");
  await settle();

  assert.deepEqual(connection.sent, [{ type: "morning_routine/update", is_on: false, entry_id: "demo" }]);
});

// Review Focus 1.
test("a loader that throws leaves the card working", async () => {
  const registry = await freshCard();
  globalThis.loadCardHelpers = async () => {
    throw new Error("moved in this release");
  };
  const { card, connection } = await mount(registry);

  byKey(card, "skip").fire("click");
  await settle();

  assert.equal(byKey(card, "routine").localName, "input");
  assert.deepEqual(connection.sent, [{ type: "morning_routine/update", skip_next: true, entry_id: "demo" }]);
});

// Review Focus 1.
test("controls that never finish loading leave the card working, and the form says so after 5 seconds", async () => {
  // The five controls exist, and the selector types never arrive.
  const { card, connection } = await mount(await freshCard(CONTROL_TAGS));

  assert.equal(byKey(card, "clock").localName, "select");
  byKey(card, "routine").fire("change");
  await settle();
  assert.deepEqual(connection.sent, [{ type: "morning_routine/update", is_on: false, entry_id: "demo" }]);

  await openForm(card);
  assert.equal(dialogOf(card).open, true);
  assert.equal(selectorWith(card, "entity"), undefined);
  mock.timers.tick(5000);
  await settle();

  assert.match(dialogOf(card).text, /This form couldn't load Home Assistant's controls\. Reload the page to try again\./);
  assert.equal(button(card, "Save"), undefined);
  assert.equal(byKey(card, "clock").localName, "select");
});

test("with ha-switch defined the card draws it, and a tap sends the change and puts the switch back", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));

  const routine = byKey(card, "routine");
  assert.equal(routine.localName, "ha-switch");
  assert.equal(routine.checked, true);
  routine.checked = false;
  routine.fire("change");

  assert.equal(routine.checked, true);
  await settle();
  assert.deepEqual(connection.sent, [{ type: "morning_routine/update", is_on: false, entry_id: "demo" }]);
});

test("a tap still sends the change when the switch drawn after it can't take focus yet", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  // Home Assistant's switch throws from focus() until it has drawn itself.
  const createElement = document.createElement;
  document.createElement = (tag) => {
    const element = createElement(tag);
    if (tag === "ha-switch") {
      element.focus = () => {
        throw new TypeError("Cannot read properties of null (reading 'focus')");
      };
    }
    return element;
  };
  const routine = byKey(card, "routine");
  card.shadowRoot.activeElement = routine;

  routine.fire("change");
  await settle();
  document.createElement = createElement;

  assert.deepEqual(connection.sent, [{ type: "morning_routine/update", is_on: false, entry_id: "demo" }]);
  assert.notEqual(byKey(card, "routine").disabled, true, "the card is not left busy");
});

test("the clock dropdown is Home Assistant's once its controls have loaded, and a choice sends the change", async () => {
  const view = viewOf({ clock_options: [{ package: "com.example.clock", name: "Example Clock" }, { package: "com.other.clock", name: "Other Clock" }] });
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS), view);

  const clock = byKey(card, "clock");
  assert.equal(clock.localName, "ha-selector");
  assert.deepEqual(clock.selector.select.options, [
    { value: "com.example.clock", label: "Example Clock" },
    { value: "com.other.clock", label: "Other Clock" },
  ]);
  assert.equal(clock.value, "com.example.clock");
  clock.fire("value-changed", { value: "com.other.clock" });
  await settle();

  assert.deepEqual(connection.sent, [{ type: "morning_routine/update", clock: "com.other.clock", entry_id: "demo" }]);
});

test("a routine with no clock chosen keeps the card's own dropdown, with its Choose a clock entry", async () => {
  const { card } = await mount(await freshCard(ALL_CONTROLS), viewOf({ clock: null }));

  const clock = byKey(card, "clock");
  assert.equal(clock.localName, "select");
  assert.equal(clock.children[0].text, "Choose a clock");
});

test("the card draws itself again with Home Assistant's controls once the known recipe has loaded them", async () => {
  const registry = await freshCard();
  globalThis.loadCardHelpers = async () => ({
    createCardElement: async () => ({
      constructor: {
        getConfigElement: async () => {
          for (const tag of ALL_CONTROLS) registry.define(tag);
        },
      },
    }),
  });
  const { card } = await mount(registry);

  assert.equal(byKey(card, "routine").localName, "ha-switch");
  assert.equal(byKey(card, "clock").localName, "ha-selector");
});

test("a step row shows the server's detail line", async () => {
  const { card } = await mount(await freshCard(), viewOf({ steps: [HALL_STEP] }));

  assert.match(card.shadowRoot.text, /Heat to 68\.3°F, cool to 74°F/);
});

test("the card registers again when Home Assistant swaps the element registry", async () => {
  const first = await freshCard();
  const swapped = new Registry();
  globalThis.customElements = swapped;
  assert.equal(swapped.get("morning-routine-card"), undefined);

  first.define("home-assistant");
  await settle();

  assert.equal(swapped.get("morning-routine-card"), first.get("morning-routine-card"));
});

// ----- The form -----

test("adding a light step with a brightness sends it", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);

  choose(card, "light.lamp");
  tick(card);
  settingSlider(card, "brightness").fire("value-changed", { value: 40 });
  await save(card);

  assert.deepEqual(connection.sent, [
    {
      type: "morning_routine/set_steps",
      entry_id: "demo",
      steps: [{ item: "light.lamp", offset_minutes: -30, action: "turn_on", brightness: 40, enabled: true }],
    },
  ]);
  assert.equal(dialogOf(card).open, false);
});

test("a light step with Brightness unticked sends no brightness, and shows what that means", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);

  choose(card, "light.lamp");
  assert.equal(settingSlider(card, "brightness"), undefined);
  assert.match(dialogOf(card).text, /as it was/);
  await save(card);

  assert.deepEqual(connection.sent[0].steps, [{ item: "light.lamp", offset_minutes: -30, action: "turn_on", enabled: true }]);
});

test("the toggle buttons choose the action, and an item with one action shows none", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);

  choose(card, "climate.hall");
  assert.equal(selectorWith(card, "button_toggle"), undefined);
  choose(card, "light.lamp");
  const toggle = selectorWith(card, "button_toggle");
  assert.deepEqual(toggle.selector.button_toggle.options, [
    { value: "turn_on", label: "Turn on" },
    { value: "turn_off", label: "Turn off" },
  ]);
  toggle.fire("value-changed", { value: "turn_off" });
  await save(card);

  assert.deepEqual(connection.sent[0].steps, [{ item: "light.lamp", offset_minutes: -30, action: "turn_off", enabled: true }]);
});

test("a range thermostat can be saved without moving a slider", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);

  choose(card, "climate.hall");
  assert.equal(settingSlider(card, "heat_to").value, 62);
  assert.deepEqual(settingSlider(card, "cool_to").selector, slider(45, 95, "°F"));
  await save(card);

  assert.deepEqual(connection.sent[0].steps, [
    { item: "climate.hall", offset_minutes: -30, action: "set_temperature", heat_to: 62, cool_to: 78, enabled: true },
  ]);
});

test("the picker offers only what the server lists, and Save is off until an item is chosen", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);

  assert.deepEqual(selectorWith(card, "entity").selector.entity.include_entities, ["light.lamp", "climate.hall"]);
  assert.equal(button(card, "Save").disabled, true);
  await save(card);
  assert.deepEqual(connection.sent, []);

  choose(card, "light.lamp");
  assert.equal(button(card, "Save").disabled, false);
});

test("a control is given back each value it reports, and an emptied number box turns Save off", async () => {
  const { card } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);
  choose(card, "climate.hall");

  const heat = settingSlider(card, "heat_to");
  heat.fire("value-changed", { value: 70.5 });
  assert.equal(heat.value, 70.5);
  assert.equal(settingSlider(card, "heat_to"), heat, "a slider that reported a value is not drawn again");

  heat.fire("value-changed", { value: undefined });
  assert.equal(button(card, "Save").disabled, true);
});

// Review Focus 3.
test("retiming a saved step sends its settings back unchanged", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS), viewOf({ steps: [HALL_STEP] }));
  await openForm(card, "name:h1");

  assert.equal(settingSlider(card, "heat_to").value, 68.3);
  settingSlider(card, "minutes").fire("value-changed", { value: 45 });
  await save(card);

  assert.deepEqual(connection.sent[0].steps, [
    { id: "h1", item: "climate.hall", offset_minutes: -45, action: "set_temperature", heat_to: 68.3, cool_to: 74, enabled: true },
  ]);
});

test("the minutes are checked before anything is sent", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);
  choose(card, "light.lamp");

  settingSlider(card, "minutes").fire("value-changed", { value: 721 });
  await save(card);
  assert.match(dialogOf(card).text, /A step can be at most 720 minutes before the alarm\./);

  settingSlider(card, "minutes").fire("value-changed", { value: undefined });
  await save(card);
  assert.match(dialogOf(card).text, /Enter a whole number of minutes\./);
  assert.deepEqual(connection.sent, []);
});

// Review Focus 2.
test("a view that drops brightness while the form is open redraws the form, says so, and Save sends no brightness", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);
  choose(card, "light.lamp");
  tick(card);
  settingSlider(card, "brightness").fire("value-changed", { value: 40 });

  connection.push(viewOf({ items: [PLAIN_LAMP, HALL] }));
  await settle();

  assert.equal(settingSlider(card, "brightness"), undefined);
  assert.match(dialogOf(card).text, /This item changed while the form was open\. Check the settings before saving\./);
  await save(card);
  assert.deepEqual(connection.sent[0].steps, [{ item: "light.lamp", offset_minutes: -30, action: "turn_on", enabled: true }]);
});

// Review Focus 2.
test("a view that removes the chosen item clears the choice, says so, and turns Save off", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);
  choose(card, "light.lamp");

  connection.push(viewOf({ items: [HALL] }));
  await settle();

  assert.equal(selectorWith(card, "entity").value, undefined);
  assert.match(dialogOf(card).text, /That choice is no longer available\. Choose again\./);
  assert.equal(button(card, "Save").disabled, true);
  await save(card);
  assert.deepEqual(connection.sent, []);
});

test("a view that changes nothing the form shows leaves its controls alone", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);
  choose(card, "light.lamp");
  const picker = selectorWith(card, "entity");

  connection.push(viewOf({ is_on: false }));
  await settle();

  assert.equal(selectorWith(card, "entity"), picker);
  assert.doesNotMatch(dialogOf(card).text, /changed/);
});

test("the form closes when someone else removes the step being edited", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS), viewOf({ steps: [HALL_STEP] }));
  await openForm(card, "name:h1");
  assert.equal(dialogOf(card).open, true);

  connection.push(viewOf());
  await settle();

  assert.equal(dialogOf(card).open, false);
});

test("a step its item can no longer show is locked: it shows what it does, and Save changes only its time", async () => {
  const brightStep = savedStep({ id: "a", item: "light.lamp", name: "Lamp", offset_minutes: -10, action: "turn_on", brightness: 40, detail: "Turn on at 40%" });
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS), viewOf({ steps: [brightStep], items: [PLAIN_LAMP] }));
  await openForm(card, "name:a");

  assert.equal(selectorWith(card, "entity"), undefined);
  assert.match(dialogOf(card).text, /Lamp/);
  assert.match(dialogOf(card).text, /Turn on at 40%/);
  assert.match(dialogOf(card).text, /What this step does can't be changed here, because the item no longer offers it\. Its time can still be changed\./);
  settingSlider(card, "minutes").fire("value-changed", { value: 5 });
  await save(card);

  assert.deepEqual(connection.sent[0].steps, [
    { id: "a", item: "light.lamp", offset_minutes: -5, action: "turn_on", brightness: 40, enabled: true },
  ]);
});

test("the server's refusal sentence is shown in the form, which stays open", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  connection.refusal = '"Heat to" must be lower than "Cool to".';
  await openForm(card);
  choose(card, "climate.hall");
  await save(card);

  assert.match(dialogOf(card).text, /"Heat to" must be lower than "Cool to"\./);
  assert.equal(dialogOf(card).open, true);
});

test("Remove step sends the list without the step", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS), viewOf({ steps: [HALL_STEP] }));
  await openForm(card, "name:h1");

  button(card, "Remove step").fire("click");
  await settle();

  assert.deepEqual(connection.sent, [{ type: "morning_routine/set_steps", entry_id: "demo", steps: [] }]);
});

test("the form draws nothing for a part it leaves out", async () => {
  const script = { item: "script.wake", name: "Wake", actions: [{ action: "run", name: "Run", settings: [] }] };
  const { card } = await mount(await freshCard(ALL_CONTROLS), viewOf({ items: [LAMP, script] }));
  await openForm(card);
  choose(card, "light.lamp");

  assert.doesNotMatch(dialogOf(card).text, /false|undefined|null/);
});

test("the note about the label shows when no labelled item is offered", async () => {
  const { card } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);

  assert.match(dialogOf(card).text, /Scripts, scenes and automations appear here once an admin gives them the "morning routine" label\./);
});

test("open controls get the newest hass", async () => {
  const { card, connection } = await mount(await freshCard(ALL_CONTROLS));
  await openForm(card);
  const newer = { connection, states: {} };

  card.hass = newer;

  assert.equal(selectorWith(card, "entity").hass, newer);
});
