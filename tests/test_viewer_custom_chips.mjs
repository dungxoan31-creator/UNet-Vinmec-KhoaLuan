import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("viewer.js provides custom clinical tag management and consistency check", () => {
  const code = fs.readFileSync(path.join(rootDir, "frontend/app/viewer.js"), "utf8");
  assert.match(code, /add-custom-chip|data-action="add-chip"/, "viewer must allow adding custom chips");
  assert.match(code, /remove-custom-chip|data-remove-chip/, "viewer must allow removing custom chips");
});
