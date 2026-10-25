import assert from "node:assert/strict";
import test from "node:test";

import { loadUncertaintyMap } from "../frontend/app/uncertainty-map.js";

test("loads a valid data-URI map without fetching from an opaque origin", async () => {
  const bitmap = { width: 512, height: 512, close() {} };
  let fetchCalls = 0;
  let decodedBlob;
  const browser = {
    fetch: async () => {
      fetchCalls++;
      throw new TypeError("Failed to fetch");
    },
    createImageBitmap: async (blob) => {
      decodedBlob = blob;
      return bitmap;
    },
  };

  const loaded = await loadUncertaintyMap(
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
    browser,
  );

  assert.equal(loaded, bitmap);
  assert.equal(fetchCalls, 0);
  assert.equal(decodedBlob.type, "image/png");
  assert.ok(decodedBlob.size > 0);
});

test("loadUncertaintyMap rejects wrong dimensions and closes the bitmap", async () => {
  const bitmap = {
    width: 1,
    height: 1,
    closed: false,
    close() {
      this.closed = true;
    },
  };
  const browser = {
    fetch: async () => ({ ok: true, blob: async () => ({}) }),
    createImageBitmap: async () => bitmap,
  };

  const loaded = await loadUncertaintyMap("data:image/png;base64,AA==", browser);

  assert.equal(loaded, null);
  assert.equal(bitmap.closed, true);
});
