import assert from "node:assert/strict";
import test from "node:test";
import {
  validatePid,
  validateFullName,
  validateBirthYear,
  validatePhone,
  validateGender,
  validateHometown,
  validateStudyDate,
  validateMeasurement,
} from "../frontend/app/form-validator.js";

test("validatePid enforces 9 digits and unicity", () => {
  assert.equal(validatePid("100000001", { existingPids: ["100000001"] }).valid, false);
  assert.equal(validatePid("100000001", { existingPids: ["100000001"], currentPid: "100000001" }).valid, true);
  assert.equal(validatePid("12345678", { existingPids: [] }).valid, false);
  assert.equal(validatePid("1234567890", { existingPids: [] }).valid, false);
  assert.equal(validatePid("100000005", { existingPids: ["100000001"] }).valid, true);
  assert.equal(validatePid("", { existingPids: [] }).valid, false);
});

test("validateFullName checks length and presence", () => {
  assert.equal(validateFullName("").valid, false);
  assert.equal(validateFullName("   ").valid, false);
  assert.equal(validateFullName("A").valid, false);
  assert.equal(validateFullName("Nguyễn Văn A").valid, true);
});

test("validateBirthYear calculates correct age", () => {
  const res = validateBirthYear(1994, 2026);
  assert.equal(res.valid, true);
  assert.equal(res.age, 32);
  assert.equal(validateBirthYear(1890, 2026).valid, false);
  assert.equal(validateBirthYear(2030, 2026).valid, false);
  assert.equal(validateBirthYear("abc", 2026).valid, false);
});

test("validatePhone cleans Vietnamese numbers", () => {
  const res = validatePhone("0912 345 678");
  assert.equal(res.valid, true);
  assert.equal(res.cleanPhone, "0912345678");
  assert.equal(validatePhone("123").valid, false);
  assert.equal(validatePhone("+84 987 654 321").valid, true);
});

test("validateGender requires valid category", () => {
  assert.equal(validateGender("female").valid, true);
  assert.equal(validateGender("male").valid, true);
  assert.equal(validateGender("other").valid, true);
  assert.equal(validateGender("unknown").valid, true);
  assert.equal(validateGender("invalid").valid, false);
  assert.equal(validateGender("").valid, false);
});

test("validateHometown validates string length", () => {
  assert.equal(validateHometown("Hà Nội").valid, true);
  assert.equal(validateHometown("").valid, false);
});

test("validateStudyDate ensures valid date string", () => {
  assert.equal(validateStudyDate("2026-11-02T10:00").valid, true);
  assert.equal(validateStudyDate("").valid, false);
  assert.equal(validateStudyDate("invalid-date").valid, false);
});

test("validateMeasurement checks boundaries", () => {
  assert.equal(validateMeasurement(45, { min: 0, max: 500 }).valid, true);
  assert.equal(validateMeasurement(-5, { min: 0, max: 500 }).valid, false);
  assert.equal(validateMeasurement(600, { min: 0, max: 500 }).valid, false);
});
