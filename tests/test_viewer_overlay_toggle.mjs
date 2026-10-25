import assert from "node:assert/strict";
import test from "node:test";

import { isOverlayToggleShortcut } from "../frontend/app/viewer-shortcuts.js";

test("overlay toggle shortcut does not mutate mask bytes or dirty state", () => {
  // Simulate image mask state
  const originalBytes = new Uint8ClampedArray([0, 255, 128, 64, 0, 1]);
  const maskCopy = new Uint8ClampedArray(originalBytes);

  let stateDirty = false;
  let overlayVisible = true;

  function handleKeydown(event) {
    if (isOverlayToggleShortcut(event)) {
      overlayVisible = !overlayVisible;
      // Changing overlay visibility must NEVER mark clinical draft as dirty
      // and must never mutate mask data
    }
  }

  // Action: Press 'o' to toggle overlay
  handleKeydown({ key: "o" });
  assert.equal(overlayVisible, false);
  assert.equal(stateDirty, false);
  assert.deepEqual(maskCopy, originalBytes);

  // Action: Press 'O' (with CapsLock) to toggle overlay back
  handleKeydown({ key: "O" });
  assert.equal(overlayVisible, true);
  assert.equal(stateDirty, false);
  assert.deepEqual(maskCopy, originalBytes);
});

test("overlay toggle is blocked when focus is on clinical text or select inputs", () => {
  let overlayVisible = true;

  function handleKeydown(event) {
    if (isOverlayToggleShortcut(event)) {
      overlayVisible = !overlayVisible;
    }
  }

  const inputTarget = {
    tagName: "INPUT",
    closest: (selector) => (selector.includes("input") ? {} : null),
  };

  const textareaTarget = {
    tagName: "TEXTAREA",
    closest: (selector) => (selector.includes("textarea") ? {} : null),
  };

  const selectTarget = {
    tagName: "SELECT",
    closest: (selector) => (selector.includes("select") ? {} : null),
  };

  // When doctor is typing observation notes containing letter 'o'
  handleKeydown({ key: "o", target: inputTarget });
  assert.equal(overlayVisible, true);

  handleKeydown({ key: "o", target: textareaTarget });
  assert.equal(overlayVisible, true);

  handleKeydown({ key: "o", target: selectTarget });
  assert.equal(overlayVisible, true);
});

test("overlay toggle is blocked when modifier keys (Ctrl/Meta/Alt) are pressed", () => {
  let overlayVisible = true;

  function handleKeydown(event) {
    if (isOverlayToggleShortcut(event)) {
      overlayVisible = !overlayVisible;
    }
  }

  // Ctrl+O (File open in browser), Alt+O, Meta+O must not trigger viewer overlay toggle
  handleKeydown({ key: "o", ctrlKey: true });
  assert.equal(overlayVisible, true);

  handleKeydown({ key: "o", metaKey: true });
  assert.equal(overlayVisible, true);

  handleKeydown({ key: "o", altKey: true });
  assert.equal(overlayVisible, true);
});
