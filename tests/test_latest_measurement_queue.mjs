import test from "node:test";
import assert from "node:assert/strict";
import { LatestMeasurementQueue } from "../frontend/app/latest-measurement-queue.js";

test("one measurement runs while intermediate queued edits are replaced", async () => {
  const calls = [];
  let resolveFirst;
  const queue = new LatestMeasurementQueue();
  queue.submit(async () => { calls.push("first"); await new Promise(resolve => { resolveFirst = resolve; }); });
  await Promise.resolve();
  queue.submit(async () => { calls.push("obsolete"); });
  queue.submit(async () => { calls.push("latest"); });
  assert.deepEqual(calls, ["first"]);
  resolveFirst();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(calls, ["first", "latest"]);
});

test("dispose prevents a queued request from starting", async () => {
  let resolveFirst;
  let secondCalled = false;
  const queue = new LatestMeasurementQueue();
  queue.submit(async () => { await new Promise(resolve => { resolveFirst = resolve; }); });
  await Promise.resolve();
  queue.submit(async () => { secondCalled = true; });
  queue.dispose();
  resolveFirst();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(secondCalled, false);
});

test("a failed measurement cannot stall the latest queued request", async () => {
  const queue = new LatestMeasurementQueue();
  const calls = [];
  queue.submit(async () => { calls.push("failed"); throw new Error("synthetic failure"); });
  queue.submit(async () => { calls.push("latest"); });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(calls, ["failed", "latest"]);
});
