import assert from 'node:assert/strict';
import test from 'node:test';
import { approvalImages } from '../frontend/app/approval-images.js';

test('approval preview closes its bitmap when canvas rendering fails', async () => {
  const originalDescriptors = new Map(
    ['Image', 'createImageBitmap', 'document'].map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]),
  );
  let closeCount = 0;
  globalThis.Image = class {
    set src(value) { this.source = value; }
    async decode() {}
  };
  globalThis.createImageBitmap = async () => ({
    width: 512,
    height: 512,
    close() { closeCount += 1; },
  });
  globalThis.document = {
    createElement() {
      return {
        width: 0,
        height: 0,
        getContext() {
          return {
            fillRect() {},
            drawImage() { throw new Error('Injected approval canvas draw failure.'); },
            createImageData(width, height) { return { data: new Uint8ClampedArray(width * height * 4) }; },
            putImageData() {},
          };
        },
        toDataURL() { return 'data:image/png;base64,test'; },
      };
    },
  };

  try {
    await assert.rejects(
      approvalImages({
        image_id: 'synthetic-approval-image',
        source: 'data:image/png;base64,synthetic',
        width: 512,
        height: 512,
        mask: new Uint8Array(512 * 512),
        aiMask: new Uint8Array(512 * 512),
      }),
      /Injected approval canvas draw failure\./,
    );
    assert.equal(closeCount, 1, 'A rejected preview must release its ImageBitmap.');
  } finally {
    for (const [name, descriptor] of originalDescriptors) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
});
