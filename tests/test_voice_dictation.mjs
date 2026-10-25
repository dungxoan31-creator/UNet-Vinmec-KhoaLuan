import assert from "node:assert/strict";
import test from "node:test";

import { bindLocalDictation } from "../frontend/app/voice-dictation.js";

function control(value = "") {
  const handlers = new Map();
  return {
    value,
    textContent: "",
    disabled: false,
    hidden: false,
    dispatched: [],
    addEventListener(type, handler) {
      handlers.set(type, handler);
    },
    removeEventListener(type) {
      handlers.delete(type);
    },
    click() {
      return handlers.get("click")?.({ preventDefault() {} });
    },
    dispatchEvent(event) {
      this.dispatched.push(event.type);
      return true;
    },
  };
}

function setup({ api = true, available = "available", supportsLocal = true } = {}) {
  const calls = { constructors: 0, starts: 0, aborts: 0, installs: 0, availableArgs: null };
  class FakeRecognition {
    static async available(options) {
      calls.availableArgs = options;
      return available;
    }
    static async install() {
      calls.installs++;
    }
    constructor() {
      calls.constructors++;
      this.localValue = false;
      FakeRecognition.lastInstance = this;
    }
    start() {
      calls.starts++;
    }
    abort() {
      calls.aborts++;
    }
  }
  if (supportsLocal) {
    Object.defineProperty(FakeRecognition.prototype, "processLocally", {
      get() {
        return this.localValue;
      },
      set(value) {
        this.localValue = value;
      },
    });
  }

  const browser = api ? { SpeechRecognition: FakeRecognition, Event } : {};
  const input = control("Ghi chú cũ");
  const recordButton = control();
  const status = control();
  const preview = control();
  const insertButton = control();
  const discardButton = control();
  const binding = bindLocalDictation({
    browser,
    input,
    recordButton,
    status,
    preview,
    insertButton,
    discardButton,
  });
  return {
    calls,
    browser,
    input,
    recordButton,
    status,
    preview,
    insertButton,
    discardButton,
    binding,
    recognition: () => calls.constructors ? browser.SpeechRecognition.lastInstance : null,
  };
}

test("unsupported speech API never constructs or starts recognition", async () => {
  const app = setup({ api: false });

  await app.recordButton.click();

  assert.match(app.status.textContent, /không khả dụng|trên thiết bị/i);
  assert.equal(app.calls.constructors, 0);
  assert.equal(app.calls.starts, 0);
});

test("unavailable offline Vietnamese never constructs, starts, or installs a language pack", async () => {
  const app = setup({ available: "downloadable" });

  await app.recordButton.click();

  assert.deepEqual(app.calls.availableArgs, { langs: ["vi-VN"], processLocally: true });
  assert.equal(app.calls.constructors, 0);
  assert.equal(app.calls.starts, 0);
  assert.equal(app.calls.installs, 0);
});

test("missing processLocally support never constructs or starts recognition", async () => {
  const app = setup({ supportsLocal: false });

  await app.recordButton.click();

  assert.equal(app.calls.constructors, 0);
  assert.equal(app.calls.starts, 0);
});

test("local transcript stays in preview until the clinician explicitly inserts it", async () => {
  const app = setup();

  await app.recordButton.click();
  const recognition = app.recognition();
  assert.equal(recognition.lang, "vi-VN");
  assert.equal(recognition.processLocally, true);
  assert.equal(app.calls.starts, 1);

  recognition.onresult({ results: [{ 0: { transcript: "Nang có vách mỏng" } }] });
  assert.equal(app.preview.textContent, "Nang có vách mỏng");
  assert.equal(app.input.value, "Ghi chú cũ");
  assert.equal(app.insertButton.disabled, false);

  app.insertButton.click();
  assert.equal(app.input.value, "Ghi chú cũ Nang có vách mỏng");
  assert.deepEqual(app.input.dispatched, ["input"]);
  assert.equal(app.preview.textContent, "");
});

test("discard clears the preview without changing the note", async () => {
  const app = setup();
  await app.recordButton.click();
  app.recognition().onresult({ results: [{ 0: { transcript: "Bản nháp" } }] });

  app.discardButton.click();

  assert.equal(app.input.value, "Ghi chú cũ");
  assert.equal(app.preview.textContent, "");
  assert.equal(app.insertButton.disabled, true);
});

test("cancel-before-result ignores a late transcript", async () => {
  const app = setup();
  await app.recordButton.click();
  const lateResult = app.recognition().onresult;

  app.binding.cancel();
  lateResult({ results: [{ 0: { transcript: "Không được chèn" } }] });

  assert.equal(app.calls.aborts, 1);
  assert.equal(app.preview.textContent, "");
  assert.equal(app.insertButton.disabled, true);
  assert.equal(app.input.value, "Ghi chú cũ");
});

test("cancel while checking offline availability prevents recognizer construction", async () => {
  let resolveAvailability;
  const availability = new Promise((resolve) => {
    resolveAvailability = resolve;
  });
  const app = setup({ available: availability });

  const starting = app.recordButton.click();
  app.binding.cancel();
  resolveAvailability("available");
  await starting;

  assert.equal(app.calls.constructors, 0);
  assert.equal(app.calls.starts, 0);
});

test("microphone denial discards transcript and does not fall back to network", async () => {
  const app = setup();
  await app.recordButton.click();
  app.recognition().onerror({ error: "not-allowed" });

  assert.match(app.status.textContent, /micro|quyền/i);
  assert.equal(app.preview.textContent, "");
  assert.equal(app.calls.installs, 0);
  assert.equal(app.input.value, "Ghi chú cũ");
});
