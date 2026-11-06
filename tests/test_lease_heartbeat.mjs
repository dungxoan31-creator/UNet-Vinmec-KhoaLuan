import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";

class Storage {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

test("late heartbeat cannot restore local lease after release or overlap", async () => {
  globalThis.localStorage = new Storage();
  globalThis.sessionStorage = new Storage();
  globalThis.window = new EventTarget();
  Object.defineProperty(globalThis, "navigator", { value: { onLine: true }, configurable: true });
  Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
  const originalInterval = globalThis.setInterval;
  const originalClear = globalThis.clearInterval;
  const originalFetch = globalThis.fetch;
  let heartbeat;
  globalThis.setInterval = callback => { heartbeat = callback; return 1; };
  globalThis.clearInterval = () => {};
  let resolveHeartbeat;
  let posts = 0;
  globalThis.fetch = async (_url, options) => {
    if (options.method === "DELETE") return new Response('{}');
    posts++;
    if (posts === 1) return Response.json({ granted: true, lease_token: "initial-token" });
    return new Promise(resolve => { resolveHeartbeat = resolve; });
  };
  try {
    const { state } = await import("../frontend/app/state.js");
    state.user = { id: "synthetic-doctor" };
    state.token = "synthetic-token";
    state.capabilities.case_leases = true;
    const { acquireLease } = await import("../frontend/app/leases.js");
    const lease = await acquireLease("synthetic-case", () => {});
    const pending = heartbeat();
    await Promise.resolve();
    await heartbeat();
    assert.equal(posts, 2, "a second heartbeat must not overlap");
    lease.release();
    resolveHeartbeat(Response.json({ granted: true, lease_token: "initial-token" }));
    await pending;
    assert.equal(localStorage.getItem("ova.lease.live.synthetic-case"), null);
    assert.equal(sessionStorage.getItem("ova.server-lease.synthetic-case"), null);
  } finally {
    globalThis.setInterval = originalInterval;
    globalThis.clearInterval = originalClear;
    globalThis.fetch = originalFetch;
  }
});

test("heartbeat failure reports lease loss and stops edit-session renewal", async () => {
  globalThis.localStorage = new Storage();
  globalThis.sessionStorage = new Storage();
  globalThis.window = new EventTarget();
  Object.defineProperty(globalThis, "navigator", { value: { onLine: true }, configurable: true });
  Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
  const originalInterval = globalThis.setInterval;
  const originalClear = globalThis.clearInterval;
  const originalFetch = globalThis.fetch;
  let heartbeat;
  globalThis.setInterval = callback => { heartbeat = callback; return 1; };
  globalThis.clearInterval = () => {};
  let posts = 0;
  globalThis.fetch = async (_url, options) => {
    if (options.method === "DELETE") return new Response(null, { status: 204 });
    posts++;
    if (posts === 1) return Response.json({ granted: true, lease_token: "renewable-lease-token" });
    return Response.json({ detail: "storage unavailable" }, { status: 503 });
  };
  try {
    const { state } = await import("../frontend/app/state.js");
    state.user = { id: "synthetic-doctor" };
    state.token = "synthetic-token";
    state.capabilities.case_leases = true;
    const { acquireLease } = await import("../frontend/app/leases.js");
    const lostMessages = [];
    const lease = await acquireLease("lease-recovery-case", message => lostMessages.push(message));

    await heartbeat();

    assert.equal(posts, 2);
    assert.equal(lostMessages.length, 1);
    assert.match(lostMessages[0], /Mất quyền giữ phiên chỉnh sửa/);
    lease.release();
  } finally {
    globalThis.setInterval = originalInterval;
    globalThis.clearInterval = originalClear;
    globalThis.fetch = originalFetch;
  }
});
