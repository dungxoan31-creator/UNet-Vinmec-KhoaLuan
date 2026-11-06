import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { DEMO_PATIENTS } from "../frontend/app/demo-patients.js";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("intake uses the facility patient-directory API and does not persist demographics in browser storage", () => {
  const intake = fs.readFileSync(path.join(rootDir, "frontend/app/intake.js"), "utf8");
  assert.match(intake, /\/api\/patient-directory/);
  assert.equal(intake.includes("localStorage"), false);
  assert.equal(intake.includes("generatePatientPid"), false);
  assert.equal(intake.includes("name=pid"), false);
});

test("synthetic demo patients contain no generated or source patient identifiers", () => {
  assert.ok(DEMO_PATIENTS.length > 0);
  assert.ok(DEMO_PATIENTS.every(patient => patient.synthetic === true && !Object.hasOwn(patient, "pid")));
});
