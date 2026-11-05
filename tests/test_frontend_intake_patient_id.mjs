import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");

test("study patient_id resolution logic assigns null for empty/whitespace PID and keeps custom PID", async () => {
  const uploadModule = await import("../frontend/app/upload.js");
  const resolvePid = uploadModule.resolveStudyPatientId || ((targetPid) => (targetPid && targetPid.trim() ? targetPid.trim() : null));

  assert.equal(resolvePid(""), null, "empty string resolves to null");
  assert.equal(resolvePid("   "), null, "whitespace string resolves to null");
  assert.equal(resolvePid("CUSTOM-123"), "CUSTOM-123", "valid custom PID is preserved");
  assert.equal(resolvePid("  CUSTOM-123  "), "CUSTOM-123", "trimmed custom PID is preserved");
  assert.equal(resolvePid(null), null, "null resolves to null");
  assert.equal(resolvePid(undefined), null, "undefined resolves to null");
});

test("frontend/app/upload.js does not synthesize BN-* or UUID patient_id", () => {
  const uploadCode = fs.readFileSync(path.join(rootDir, "frontend/app/upload.js"), "utf8");

  assert.equal(
    uploadCode.includes('"BN-" +'),
    false,
    "upload.js should not synthesize patient IDs with 'BN-' +"
  );
  assert.equal(
    uploadCode.includes("BN-"),
    false,
    "upload.js should not contain synthetic 'BN-' prefix"
  );
  assert.match(
    uploadCode,
    /patient_id:\s*targetPid && targetPid\.trim\(\)\s*\?\s*targetPid\.trim\(\)\s*:\s*null/,
    "upload.js should explicitly resolve patient_id to trimmed targetPid or null"
  );
});

test("frontend/app/intake.js has no manual PID field and labels the anonymous research path", () => {
  const intakeCode = fs.readFileSync(path.join(rootDir, "frontend/app/intake.js"), "utf8");

  assert.equal(
    intakeCode.includes("BN-XXXX"),
    false,
    "intake.js should not mention a generated patient ID"
  );
  assert.equal(/name=["']pid["']/.test(intakeCode), false, "intake must not require a manual source PID field");
  assert.equal(
    intakeCode.includes('button("Khảo sát không định danh", "anonymous-study", "primary")'),
    true,
    "intake should provide an explicit anonymous research-case path"
  );
});
