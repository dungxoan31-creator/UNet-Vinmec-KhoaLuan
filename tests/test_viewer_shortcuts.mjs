import assert from "node:assert/strict";
import test from "node:test";

import {
  getReportShortcutHash,
  isFastAdvanceShortcut,
  isHelpShortcut,
  isOverlayToggleShortcut,
  getOradsShortcutValue,
  isAutoZoomShortcut,
  isUndoShortcut,
} from "../frontend/app/viewer-shortcuts.js";

test("Ctrl+P and Meta+P open the report hash for the active study", () => {
  assert.equal(
    getReportShortcutHash({ key: "p", ctrlKey: true }, "study 1/left"),
    "#report/study%201%2Fleft?print=1",
  );
  assert.equal(
    getReportShortcutHash({ key: "P", metaKey: true }, "study-2"),
    "#report/study-2?print=1",
  );
});

test("does not consume plain or extra-modifier P keys", () => {
  for (const event of [
    { key: "p" },
    { key: "p", ctrlKey: true, shiftKey: true },
    { key: "p", metaKey: true, altKey: true },
    { key: "x", ctrlKey: true },
  ])
    assert.equal(getReportShortcutHash(event, "study-1"), null);
});

test("does not intercept composition or editable targets", () => {
  const editable = { closest: () => ({}) };
  const contentEditable = { isContentEditable: true, closest: () => null };
  assert.equal(
    getReportShortcutHash({ key: "p", ctrlKey: true, isComposing: true }, "study-1"),
    null,
  );
  assert.equal(
    getReportShortcutHash({ key: "p", ctrlKey: true, target: editable }, "study-1"),
    null,
  );
  assert.equal(
    getReportShortcutHash({ key: "p", ctrlKey: true, target: contentEditable }, "study-1"),
    null,
  );
});

test("does not create a report route without a study id", () => {
  assert.equal(getReportShortcutHash({ key: "p", ctrlKey: true }, ""), null);
  assert.equal(getReportShortcutHash({ key: "p", ctrlKey: true }, null), null);
});

test("isOverlayToggleShortcut detects plain O and o, rejecting modifiers or editable targets", () => {
  assert.equal(isOverlayToggleShortcut({ key: "o" }), true);
  assert.equal(isOverlayToggleShortcut({ key: "O" }), true);

  assert.equal(isOverlayToggleShortcut({ key: "o", ctrlKey: true }), false);
  assert.equal(isOverlayToggleShortcut({ key: "o", metaKey: true }), false);
  assert.equal(isOverlayToggleShortcut({ key: "o", altKey: true }), false);
  assert.equal(isOverlayToggleShortcut({ key: "o", isComposing: true }), false);

  const editable = { closest: () => ({}) };
  assert.equal(isOverlayToggleShortcut({ key: "o", target: editable }), false);
});

test("isFastAdvanceShortcut detects Shift+Enter, rejecting plain Enter or other modifiers", () => {
  assert.equal(isFastAdvanceShortcut({ key: "Enter", shiftKey: true }), true);
  assert.equal(isFastAdvanceShortcut({ key: "enter", shiftKey: true }), true);

  assert.equal(isFastAdvanceShortcut({ key: "Enter" }), false);
  assert.equal(isFastAdvanceShortcut({ key: "Enter", shiftKey: true, ctrlKey: true }), false);
  assert.equal(isFastAdvanceShortcut({ key: "Enter", shiftKey: true, metaKey: true }), false);

  const editable = { closest: () => ({}) };
  assert.equal(isFastAdvanceShortcut({ key: "Enter", shiftKey: true, target: editable }), false);
});

test("isHelpShortcut detects ? key and rejects editable inputs", () => {
  assert.equal(isHelpShortcut({ key: "?" }), true);
  assert.equal(isHelpShortcut({ key: "?", ctrlKey: true }), false);
  assert.equal(isHelpShortcut({ key: "/", shiftKey: true }), false);

  const editable = { closest: () => ({}) };
  assert.equal(isHelpShortcut({ key: "?", target: editable }), false);
});

test("getOradsShortcutValue assigns O-RADS 1 through 5, rejecting editable targets", () => {
  assert.equal(getOradsShortcutValue({ key: "1" }), "O-RADS 1");
  assert.equal(getOradsShortcutValue({ key: "2" }), "O-RADS 2");
  assert.equal(getOradsShortcutValue({ key: "3" }), "O-RADS 3");
  assert.equal(getOradsShortcutValue({ key: "4" }), "O-RADS 4");
  assert.equal(getOradsShortcutValue({ key: "5" }), "O-RADS 5");
  assert.equal(getOradsShortcutValue({ key: "2", altKey: true }), "O-RADS 2");
  assert.equal(getOradsShortcutValue({ key: "0", altKey: true }), "O-RADS 0");

  assert.equal(getOradsShortcutValue({ key: "9" }), null);
  assert.equal(getOradsShortcutValue({ key: "1", ctrlKey: true }), null);
  const editable = { closest: () => ({}) };
  assert.equal(getOradsShortcutValue({ key: "1", target: editable }), null);
});

test("isAutoZoomShortcut detects plain A and a", () => {
  assert.equal(isAutoZoomShortcut({ key: "a" }), true);
  assert.equal(isAutoZoomShortcut({ key: "A" }), true);
  assert.equal(isAutoZoomShortcut({ key: "a", ctrlKey: true }), false);
});

test("isUndoShortcut detects plain Z or Ctrl+Z", () => {
  assert.equal(isUndoShortcut({ key: "z" }), true);
  assert.equal(isUndoShortcut({ key: "Z" }), true);
  assert.equal(isUndoShortcut({ key: "z", ctrlKey: true }), true);
  assert.equal(isUndoShortcut({ key: "z", altKey: true }), false);
});
