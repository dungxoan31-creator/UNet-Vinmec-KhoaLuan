import test from "node:test";
import assert from "node:assert/strict";
import { state } from "../frontend/app/state.js";
import { protectedImage, request, uploadFile } from "../frontend/app/api.js";

test("late response from an older token is discarded even for the same user", async () => {
  const oldFetch = globalThis.fetch;
  const oldNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  let deliver;
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { onLine: true } });
  state.user = { id: "doctor-a" };
  state.token = "old-token";
  globalThis.fetch = () => new Promise(resolve => { deliver = resolve; });
  try {
    const pending = request("/api/example");
    state.token = "new-token";
    deliver(Response.json({ value: "stale" }));
    await assert.rejects(pending, error => error.name === "AbortError");
  } finally {
    globalThis.fetch = oldFetch;
    if (oldNavigator) Object.defineProperty(globalThis, "navigator", oldNavigator);
    else delete globalThis.navigator;
    state.user = null;
    state.token = null;
  }
});

test("a stale 401 cannot expire the replacement session", async () => {
  const oldFetch = globalThis.fetch;
  const oldWindow = globalThis.window;
  const oldNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  let deliver;
  let expired = false;
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { onLine: true } });
  globalThis.window = { dispatchEvent() { expired = true; } };
  state.user = { id: "doctor-a" };
  state.token = "old-token";
  globalThis.fetch = () => new Promise(resolve => { deliver = resolve; });
  try {
    const pending = request("/api/example");
    state.token = "new-token";
    deliver(new Response("{}", { status: 401 }));
    await assert.rejects(pending, error => error.name === "AbortError");
    assert.equal(expired, false);
  } finally {
    globalThis.fetch = oldFetch;
    globalThis.window = oldWindow;
    if (oldNavigator) Object.defineProperty(globalThis, "navigator", oldNavigator);
    else delete globalThis.navigator;
    state.user = null;
    state.token = null;
  }
});

test("transport timeout is surfaced as a retryable API error", async () => {
  const oldFetch = globalThis.fetch;
  const oldNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  let aborted = false;
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { onLine: true },
  });
  globalThis.fetch = (_path, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => {
      aborted = true;
      reject(new DOMException("Request aborted", "AbortError"));
    }, { once: true });
  });
  try {
    await assert.rejects(
      request("/api/slow", { signal: new AbortController().signal, timeoutMs: 5 }),
      error => error.status === 408 && /phản hồi quá lâu/i.test(error.message),
    );
    assert.equal(aborted, true, "The timed out request must abort its underlying fetch.");
  } finally {
    globalThis.fetch = oldFetch;
    if (oldNavigator) Object.defineProperty(globalThis, "navigator", oldNavigator);
    else delete globalThis.navigator;
  }
});

test("protected image timeout aborts the fetch and surfaces a retryable 408", async () => {
  const oldFetch = globalThis.fetch;
  const oldToken = state.token;
  const oldRouteController = state.routeController;
  let aborted = false;
  state.token = "image-timeout-test-token";
  state.routeController = null;
  globalThis.fetch = (_path, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => {
      aborted = true;
      reject(new DOMException("Request aborted", "AbortError"));
    }, { once: true });
  });
  try {
    await assert.rejects(
      protectedImage("/api/images/slow/source.png", 5),
      error => error.status === 408 && /phản hồi quá lâu/i.test(error.message),
    );
    assert.equal(aborted, true, "A timed out image request must abort its underlying fetch.");
  } finally {
    globalThis.fetch = oldFetch;
    state.token = oldToken;
    if (oldRouteController === undefined) delete state.routeController;
    else state.routeController = oldRouteController;
  }
});

test("protectedImage dispatches ova:expired event on 401 response", async () => {
  const oldFetch = globalThis.fetch;
  const oldWindow = globalThis.window;
  const oldToken = state.token;
  let expiredFired = false;
  globalThis.window = new EventTarget();
  const listener = () => { expiredFired = true; };
  globalThis.window.addEventListener("ova:expired", listener);
  state.token = "image-auth-test-token";
  globalThis.fetch = () => Promise.resolve(new Response("{}", { status: 401 }));
  try {
    await protectedImage("/api/images/unauthorized/source.png");
    assert.fail("Should have thrown");
  } catch (err) {
    assert.equal(err.status, 401);
    assert.match(err.message, /hết hạn/i);
    assert.equal(expiredFired, true);
  } finally {
    globalThis.window?.removeEventListener?.("ova:expired", listener);
    globalThis.fetch = oldFetch;
    globalThis.window = oldWindow;
    state.token = oldToken;
  }
});

test("upload sends a stable idempotency key and surfaces an abortable retryable timeout", async () => {
  const oldXhr = globalThis.XMLHttpRequest;
  const oldToken = state.token;
  let xhr;
  class FakeXhr {
    constructor() {
      this.upload = {};
      this.headers = {};
      xhr = this;
    }
    open(method, path) { this.method = method; this.path = path; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    send(form) { this.form = form; }
    abort() { this.aborted = true; this.onabort?.(); }
  }
  globalThis.XMLHttpRequest = FakeXhr;
  state.token = "upload-timeout-test-token";
  try {
    const controller = new AbortController();
    const resultPromise = uploadFile(
      new Blob(["synthetic-ultrasound-bytes"], { type: "image/png" }),
      "synthetic-study",
      "L",
      () => {},
      controller.signal,
      null,
      { "X-Case-Lease-Token": "synthetic-lease" },
      "b8ee983e-ccea-4f8c-9065-42b1183f37b6",
    );
    assert.equal(xhr.method, "POST");
    assert.equal(xhr.path, "/api/upload");
    assert.equal(xhr.timeout, 600_000);
    assert.equal(xhr.headers["Idempotency-Key"], "b8ee983e-ccea-4f8c-9065-42b1183f37b6");
    assert.equal(xhr.headers["X-Case-Lease-Token"], "synthetic-lease");
    xhr.status = 200;
    xhr.responseText = '{"image_id":"synthetic-image"}';
    xhr.onload();
    assert.deepEqual(await resultPromise, { image_id: "synthetic-image" });

    const timeoutPromise = uploadFile(
      new Blob(["synthetic-ultrasound-bytes"], { type: "image/png" }),
      "synthetic-study",
      "L",
      () => {},
      new AbortController().signal,
      null,
      {},
      "b8ee983e-ccea-4f8c-9065-42b1183f37b6",
    );
    xhr.ontimeout();
    await assert.rejects(
      timeoutPromise,
      error => error.status === 408 && /10 phút/.test(error.message),
    );

    const cancelled = new AbortController();
    cancelled.abort();
    const cancelledPromise = uploadFile(
      new Blob(["synthetic-ultrasound-bytes"], { type: "image/png" }),
      "synthetic-study",
      "L",
      () => {},
      cancelled.signal,
    );
    await assert.rejects(cancelledPromise, error => error.name === "AbortError");
    assert.equal(xhr.form, undefined, "An already-cancelled upload must not be sent.");
  } finally {
    globalThis.XMLHttpRequest = oldXhr;
    state.token = oldToken;
  }
});
