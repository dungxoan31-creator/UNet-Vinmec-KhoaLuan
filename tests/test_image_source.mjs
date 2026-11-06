import test from "node:test";
import assert from "node:assert/strict";
import { imageSourceBitmap } from "../frontend/app/image-source.js";

test("blob image sources decode through img-src without fetch(connect-src)", async () => {
  const originalImage = globalThis.Image;
  const originalCreateImageBitmap = globalThis.createImageBitmap;
  const originalFetch = globalThis.fetch;
  const decoded = { source: "blob:https://app.invalid/image" };
  let createdFrom;

  class ImageMock {
    decoding = "";
    src = "";
    async decode() {
      assert.equal(this.src, decoded.source);
    }
  }

  globalThis.Image = ImageMock;
  globalThis.createImageBitmap = async (source) => {
    createdFrom = source;
    return decoded;
  };
  globalThis.fetch = async () => {
    throw new Error("Blob URLs must not be fetched through connect-src.");
  };

  try {
    const result = await imageSourceBitmap(decoded.source);
    assert.equal(result, decoded);
    assert.ok(createdFrom instanceof ImageMock);
  } finally {
    globalThis.Image = originalImage;
    globalThis.createImageBitmap = originalCreateImageBitmap;
    globalThis.fetch = originalFetch;
  }
});
