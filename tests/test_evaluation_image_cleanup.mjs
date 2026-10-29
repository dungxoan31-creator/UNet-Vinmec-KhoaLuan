import assert from 'node:assert/strict';
import test from 'node:test';
import { binaryErrorMap } from '../frontend/app/evaluation-images.js';

test('binary error map closes the bitmap that loaded before its pair failed', async () => {
  const originalFetch = Object.getOwnPropertyDescriptor(globalThis, 'fetch');
  const originalCreate = Object.getOwnPropertyDescriptor(globalThis, 'createImageBitmap');
  let closeCount = 0;
  globalThis.fetch = async source => ({ blob: async () => source });
  globalThis.createImageBitmap = async source => {
    if (source === 'prediction-mask') throw new Error('Injected prediction-mask decode failure.');
    return { width: 512, height: 512, close() { closeCount += 1; } };
  };

  try {
    await assert.rejects(
      binaryErrorMap('ground-truth-mask', 'prediction-mask'),
      /Injected prediction-mask decode failure\./,
    );
    assert.equal(closeCount, 1, 'A fulfilled bitmap must be closed even when its pair fails to decode.');
  } finally {
    if (originalFetch) Object.defineProperty(globalThis, 'fetch', originalFetch);
    else delete globalThis.fetch;
    if (originalCreate) Object.defineProperty(globalThis, 'createImageBitmap', originalCreate);
    else delete globalThis.createImageBitmap;
  }
});
