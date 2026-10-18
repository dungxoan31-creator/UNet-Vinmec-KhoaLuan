"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

function testViewerBusyAndReadonlyGuards() {
  const viewerSrc = fs.readFileSync(path.join(__dirname, "../frontend/app/viewer.js"), "utf8");
  const reviewSrc = fs.readFileSync(path.join(__dirname, "../frontend/app/review.js"), "utf8");

  // FE-01: Verify busy and readonly guards exist on iotaMorphology and oradsScore
  assert.ok(
    viewerSrc.includes('$("#iotaMorphology").disabled = readonly'),
    "iotaMorphology must be disabled when readonly is true"
  );
  assert.ok(
    viewerSrc.includes('$("#oradsScore").disabled = readonly'),
    "oradsScore must be disabled when readonly is true"
  );
  assert.ok(
    viewerSrc.includes("if (state.busy || readonly)"),
    "Field handlers must guard against modifications during state.busy"
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
