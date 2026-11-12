// The card element against a connection that behaves like Home Assistant's when it drops.
// The connection copies how home-assistant-js-websocket treats a subscription made with
// resubscribe: false: it is never rejected and never sent again after a drop.
import assert from "node:assert/strict";
import { mock, test } from "node:test";

mock.timers.enable({ apis: ["setTimeout"] });

class FakeElement {
  constructor() {
    this.children = [];
    this.attributes = {};
    this.open = false;
  }
  addEventListener() {}
  setAttribute(key, value) {
    this.attributes[key] = value;
  }
  getAttribute(key) {
    return this.attributes[key] ?? null;
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  querySelectorAll() {
    return [];
  }
  contains() {
    return false;
  }
  close() {
    this.open = false;
  }
  showModal() {
    this.open = true;
  }
}

globalThis.HTMLElement = class {
  constructor() {
    this.isConnected = false;
  }
  attachShadow() {
    this.shadowRoot = new FakeElement();
    this.shadowRoot.activeElement = null;
    return this.shadowRoot;
  }
};
globalThis.document = { createElement: () => new FakeElement() };
globalThis.window = globalThis;
let Card;
globalThis.customElements = {
  get: () => undefined,
  define: (_name, element) => {
    Card = element;
  },
};
await import("../../custom_components/morning_routine/www/morning-routine-card.js");

const VIEW = {
  entry_id: "demo",
  title: "Test routine",
  is_on: true,
  skip_next: false,
  clock: "com.example.clock",
  clock_options: [{ package: "com.example.clock", name: "Example Clock" }],
  steps: [],
  items: [],
  problems: [],
  min_offset_minutes: -720,
  max_offset_minutes: 60,
};

class Connection {
  constructor() {
    this.connected = true;
    this.commands = new Map();
    this.nextId = 1;
    this.readyListeners = [];
    this.routineLoaded = true;
    this.holdAnswers = false;
    this.subscribesSent = 0;
  }
  addEventListener(type, listener) {
    if (type === "ready") this.readyListeners.push(listener);
  }
  removeEventListener(_type, listener) {
    this.readyListeners = this.readyListeners.filter((entry) => entry !== listener);
  }
  sendMessage(_message, id) {
    if (!this.connected) throw new Error("not connected");
    this.subscribesSent += 1;
    const info = this.commands.get(id);
    if (this.holdAnswers) return;
    if (this.routineLoaded) {
      info.resolve();
      setImmediate(() => info.callback({ view: VIEW }));
    } else {
      this.commands.delete(id);
      info.reject({ code: "not_found" });
    }
  }
  async sendMessagePromise() {
    return null;
  }
  async subscribeMessage(callback, message, options) {
    let info;
    await new Promise((resolve, reject) => {
      const id = this.nextId++;
      info = {
        resolve,
        reject,
        callback,
        subscribe: options?.resubscribe !== false ? () => this.subscribeMessage(callback, message, options) : undefined,
        unsubscribe: async () => {
          this.commands.delete(id);
        },
      };
      this.commands.set(id, info);
      try {
        this.sendMessage(message, id);
      } catch {
        // The library swallows this too.
      }
    });
    return () => info.unsubscribe();
  }
  drop() {
    const old = this.commands;
    this.commands = new Map();
    this.connected = false;
    old.forEach((info) => {
      if (!("subscribe" in info)) info.reject({ code: 3 });
    });
  }
  comeBack() {
    this.connected = true;
    this.readyListeners.forEach((listener) => listener(this));
  }
}

const settle = () => new Promise((resolve) => setImmediate(() => setImmediate(resolve)));
const shown = (card) => (card._view ? "view" : card._unavailable ? "unavailable" : "blank");

function mount(connection) {
  const card = new Card();
  card.setConfig({ routine: "demo" });
  card.isConnected = true;
  card.connectedCallback();
  card.hass = { connection };
  return card;
}

async function aMinuteLater(card, connection) {
  await settle();
  for (let tick = 0; tick < 6; tick += 1) {
    mock.timers.tick(10000);
    card.hass = { connection };
    await settle();
  }
}

test("a card with a view gets it back after the connection drops and returns", async () => {
  const connection = new Connection();
  const card = mount(connection);
  await settle();
  assert.equal(shown(card), "view");

  connection.drop();
  card.hass = { connection };
  await settle();
  connection.comeBack();
  await aMinuteLater(card, connection);

  assert.equal(shown(card), "view");
  assert.equal(connection.subscribesSent, 2);
});

test("a card that was retrying while the connection was down recovers when the routine is back", async () => {
  const connection = new Connection();
  connection.routineLoaded = false;
  const card = mount(connection);
  await settle();
  assert.equal(shown(card), "unavailable");

  connection.drop();
  mock.timers.tick(10000);
  await settle();
  connection.routineLoaded = true;
  connection.comeBack();
  await aMinuteLater(card, connection);

  assert.equal(shown(card), "view");
});

test("a card created while the connection is down shows the routine once it returns", async () => {
  const connection = new Connection();
  connection.drop();
  const card = mount(connection);
  await settle();

  connection.comeBack();
  await aMinuteLater(card, connection);

  assert.equal(shown(card), "view");
});

test("a card whose first subscribe was cut off by a drop shows the routine once it returns", async () => {
  const connection = new Connection();
  connection.holdAnswers = true;
  const card = mount(connection);
  await settle();

  connection.drop();
  connection.holdAnswers = false;
  connection.comeBack();
  await aMinuteLater(card, connection);

  assert.equal(shown(card), "view");
});

test("a routine that stays away is asked for again every 10 seconds, and not more often", async () => {
  const connection = new Connection();
  connection.routineLoaded = false;
  const card = mount(connection);
  await aMinuteLater(card, connection);

  assert.equal(shown(card), "unavailable");
  assert.equal(connection.subscribesSent, 7);
});

test("leaving the page stops the retries", async () => {
  const connection = new Connection();
  connection.routineLoaded = false;
  const card = mount(connection);
  await settle();
  const sent = connection.subscribesSent;

  card.isConnected = false;
  card.disconnectedCallback();
  mock.timers.tick(60000);
  await settle();

  assert.equal(connection.subscribesSent, sent);
  assert.equal(connection.readyListeners.length, 0);
});
