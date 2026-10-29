"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function testViewerBusyAndReadonlyGuards() {
  const viewerSrc = fs.readFileSync(path.join(__dirname, "../frontend/app/viewer.js"), "utf8");
  const reviewSrc = fs.readFileSync(path.join(__dirname, "../frontend/app/review.js"), "utf8");

  // FE-01: Verify clinical fields are disabled whenever the edit surface is busy or readonly.
  assert.ok(
    viewerSrc.includes('["notes", "morphology", "iotaMorphology", "oradsScore", "reviewContentAck"]'),
    "Clinical inputs must be included in the shared edit-state guard"
  );
  assert.ok(
    viewerSrc.includes("const blocked = !editable || state.busy || selecting || !image || disposed"),
    "Clinical inputs must be blocked while busy, selecting, disposed, or readonly"
  );
  assert.ok(
    viewerSrc.includes("if (state.busy || !canEditCanvas()"),
    "Canvas handlers must guard against modifications during state.busy or readonly"
  );
  assert.equal(
    (viewerSrc.match(/\$\("\[data-action=save-review\]"\)\.disabled\s*=\s*readonly\s*\|\|\s*!c\.images\.every/g) || []).length,
    0,
    "Save review must remain disabled while state.busy is true, including after asynchronous image selection"
  );

  // FE-01: Verify review save compares current fields against snapshot before clearing draft
  assert.ok(
    reviewSrc.includes("hasPendingChangesAfterSnapshot"),
    "review.js must check hasPendingChangesAfterSnapshot before clearing draft"
  );
  assert.ok(
    reviewSrc.includes("state.dirty = true"),
    "review.js must preserve state.dirty = true if newer edits exist"
  );

  console.log("PASS: test_fe_01_save_race_guard");
}

testViewerBusyAndReadonlyGuards();
