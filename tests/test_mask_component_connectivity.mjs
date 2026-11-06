import test from "node:test";
import assert from "node:assert/strict";
import { components } from "../frontend/app/mask-tools.js";

test("diagonal foreground contact is one component, matching OpenCV contours", () => {
  const mask = new Uint8Array(512 * 512);
  mask[10 * 512 + 10] = 1;
  mask[11 * 512 + 11] = 1;
  mask[50 * 512 + 50] = 1;
  const groups = components(mask);
  assert.equal(groups.length, 2);
  assert.deepEqual(groups.map(group => group.length).sort(), [1, 2]);
});

test("diagonal neighbours do not wrap across the image edge", () => {
  const mask = new Uint8Array(512 * 512);
  mask[10 * 512 + 511] = 1;
  mask[11 * 512] = 1;
  assert.equal(components(mask).length, 2);
});
