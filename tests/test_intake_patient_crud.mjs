import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("intake.js implements facility patient CRUD without source PID entry", () => {
  const code = fs.readFileSync(path.join(rootDir, "frontend/app/intake.js"), "utf8");
  assert.match(code, /data-edit-patient/, "intake.js must have data-edit-patient buttons");
  assert.match(code, /data-delete-patient/, "intake.js must have data-delete-patient buttons");
  assert.match(code, /validateFullName/, "intake.js must validate patient names");
  assert.match(code, /validateBirthYear/, "intake.js must validate optional birth year");
  assert.doesNotMatch(code, /name=["']pid["']/, "intake must not require a source PID");
  assert.match(code, /form-validator\.js/, "intake.js must import form-validator.js");
});
