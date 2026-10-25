import test from "node:test";
import assert from "node:assert/strict";
import { floodFill, components, cleanMask } from "../frontend/app/mask-tools.js";

test("floodFill fills enclosed region without leaking", () => {
  const mask = new Uint8Array(512 * 512);

  // Draw a 10x10 square border of value 1 from (20,20) to (30,30)
  for (let x = 20; x <= 30; x++) {
    mask[20 * 512 + x] = 1;
    mask[30 * 512 + x] = 1;
  }
  for (let y = 20; y <= 30; y++) {
    mask[y * 512 + 20] = 1;
    mask[y * 512 + 30] = 1;
  }

  // Click at (25, 25) inside the border
  const filled = floodFill(mask, 25, 25, 1);

  // Interior should be completely filled
  for (let y = 21; y < 30; y++) {
    for (let x = 21; x < 30; x++) {
      assert.equal(filled[y * 512 + x], 1, `Interior pixel (${x}, ${y}) should be filled`);
    }
  }

  // Exterior should remain 0
  assert.equal(filled[15 * 512 + 15], 0, "Exterior pixel should remain 0");
  assert.equal(filled[35 * 512 + 35], 0, "Exterior pixel should remain 0");
});

test("floodFill returns original mask when target matches fillVal or coordinates are out-of-bounds", () => {
  const mask = new Uint8Array(512 * 512);
  mask[10 * 512 + 10] = 1;

  // Clicking on already 1
  const res1 = floodFill(mask, 10, 10, 1);
  assert.equal(res1, mask);

  // Out of bounds coordinates
  const res2 = floodFill(mask, -5, 10, 1);
  assert.equal(res2, mask);
  const res3 = floodFill(mask, 512, 10, 1);
  assert.equal(res3, mask);
});
