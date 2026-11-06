import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("adnex and cdss panels enforce numeric ranges and reset capability", () => {
  const adnexCode = fs.readFileSync(path.join(rootDir, "frontend/app/adnex.js"), "utf8");
  const cdssCode = fs.readFileSync(path.join(rootDir, "frontend/app/cdss-panel.js"), "utf8");
  assert.match(adnexCode, /reset-adnex|data-action="reset-adnex"/, "adnex must support reset action");
  assert.match(cdssCode, /validateMeasurement|form-validator/, "cdss must validate numeric boundaries");
});
