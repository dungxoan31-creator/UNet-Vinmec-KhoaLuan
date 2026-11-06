import assert from "node:assert/strict";
import test from "node:test";

import { getLateralityHint, suggestLaterality } from "../frontend/app/laterality-hint.js";

test("suggests sides from exact filename tokens after path and extension normalization", () => {
  assert.equal(suggestLaterality("C:\\ultrasound\\Case_LEFT.png"), "L");
  assert.equal(suggestLaterality("study_L.png"), "L");
  assert.equal(suggestLaterality("case-right.DCM"), "R");
  assert.equal(suggestLaterality("study_R.png"), "R");
  assert.equal(suggestLaterality("ovary_trái.jpeg"), "L");
  assert.equal(suggestLaterality("ovary-phải.jpg"), "R");
});

test("does not match side tokens embedded in longer words", () => {
  assert.equal(suggestLaterality("brightful_clearance_leftish.png"), null);
  assert.equal(suggestLaterality("ovaryLRscan.dcm"), null);
});

test("returns no suggestion for missing or conflicting tokens", () => {
  assert.equal(suggestLaterality("pelvic-ultrasound.png"), null);
  assert.equal(suggestLaterality("left_right.png"), null);
  assert.equal(suggestLaterality(""), null);
});

test("hint reports mismatch without returning or repeating the filename", () => {
  const filename = "private-patient-left.png";
  const hint = getLateralityHint(filename, "R");

  assert.deepEqual(Object.keys(hint).sort(), ["message", "mismatch", "suggestedSide"]);
  assert.equal(hint.suggestedSide, "L");
  assert.equal(hint.mismatch, true);
  assert.match(hint.message, /đã chọn .*phải/i);
  assert.equal(hint.message.includes(filename), false);
  assert.equal(getLateralityHint("unknown.png", "L"), null);
});
