"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const viewerSrc = fs.readFileSync(path.join(__dirname, "../frontend/app/viewer.js"), "utf8");
const unguardedSaveButtonAssignments = viewerSrc.match(
  /\$\("\[data-action=save-review\]"\)\.disabled\s*=\s*readonly\s*\|\|\s*!c\.images\.every/g,
) || [];

assert.equal(
  unguardedSaveButtonAssignments.length,
  0,
  "Save review must remain disabled while state.busy is true, including after asynchronous image selection",
);
console.log("PASS: save-review remains disabled during in-flight work");
