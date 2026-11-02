import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("intake.js implements edit and delete buttons in patient table", () => {
  const code = fs.readFileSync(path.join(rootDir, "frontend/app/intake.js"), "utf8");
  assert.match(code, /data-edit-patient/, "intake.js must have data-edit-patient buttons");
  assert.match(code, /data-delete-patient/, "intake.js must have data-delete-patient buttons");
  assert.match(code, /validatePid/, "intake.js must import or use validatePid");
  assert.match(code, /form-validator\.js/, "intake.js must import form-validator.js");
});
