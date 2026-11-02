import assert from "node:assert/strict";
import test from "node:test";
import { createDemoPatientStore } from "../frontend/app/intake-session.js";
import {
  validatePid,
  validateFullName,
  validateBirthYear,
  validatePhone,
  validateGender,
  validateHometown,
  validateNationalId,
} from "../frontend/app/form-validator.js";

function mockStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

test("end-to-end patient lifecycle: add with validation, edit, and delete", () => {
  const storage = mockStorage();
  const store = createDemoPatientStore([], () => storage);
  const key = "e2e-patients";

  // 1. Validate inputs before adding
  const pid = "100000009";
  const name = "Lê Thị Thảo";
  const birthYear = 1995;
  const phone = "0987654321";
  const gender = "female";
  const hometown = "Đà Nẵng";
  const nationalId = "001200009999";

  assert.equal(validatePid(pid, { existingPids: [] }).valid, true);
  assert.equal(validateFullName(name).valid, true);
  assert.equal(validateNationalId(nationalId).valid, true);
  const yearRes = validateBirthYear(birthYear, 2026);
  assert.equal(yearRes.valid, true);
  assert.equal(yearRes.age, 31);
  assert.equal(validatePhone(phone).valid, true);
  assert.equal(validateGender(gender).valid, true);
  assert.equal(validateHometown(hometown).valid, true);

  // 2. Add patient
  store.add(key, {
    pid,
    name,
    national_id: nationalId,
    age: yearRes.age,
    birth_year: birthYear,
    phone,
    gender,
    hometown,
    synthetic: false,
  });

  const listAfterAdd = store.read(key);
  assert.equal(listAfterAdd.length, 1);
  assert.equal(listAfterAdd[0].pid, pid);
  assert.equal(listAfterAdd[0].national_id, nationalId);

  // 3. Edit patient (update hometown, phone, & passport)
  const updatedPhoneRes = validatePhone("0912345678");
  assert.equal(updatedPhoneRes.valid, true);
  const updatedPassportRes = validateNationalId("B9876543");
  assert.equal(updatedPassportRes.valid, true);

  store.update(key, pid, {
    hometown: "TP. Hồ Chí Minh",
    phone: updatedPhoneRes.cleanPhone,
    national_id: updatedPassportRes.cleanId,
  });

  const patientAfterEdit = store.get(key, pid);
  assert.equal(patientAfterEdit.hometown, "TP. Hồ Chí Minh");
  assert.equal(patientAfterEdit.phone, "0912345678");
  assert.equal(patientAfterEdit.national_id, "B9876543");

  // 4. Delete patient
  store.remove(key, pid);
  assert.equal(store.read(key).length, 0);
  assert.equal(store.get(key, pid), undefined);
});
