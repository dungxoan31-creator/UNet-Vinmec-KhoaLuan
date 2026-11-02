import assert from "node:assert/strict";
import test from "node:test";
import { createDemoPatientStore } from "../frontend/app/intake-session.js";

function mockStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

test("demo patient store supports update, delete, add, and get operations", () => {
  const storage = mockStorage();
  const store = createDemoPatientStore(
    [{ pid: "100000001", name: "Nguyễn Minh Anh", age: 32 }],
    () => storage
  );
  const key = "test-patients";

  // Read initial
  assert.equal(store.read(key).length, 1);

  // Add
  store.add(key, { pid: "100000002", name: "Trần Thu Hà", age: 41 });
  assert.equal(store.read(key).length, 2);
  assert.equal(store.get(key, "100000002").name, "Trần Thu Hà");

  // Update
  store.update(key, "100000001", { name: "Nguyễn Minh Anh (Đã sửa)", age: 33 });
  const updated = store.get(key, "100000001");
  assert.equal(updated.name, "Nguyễn Minh Anh (Đã sửa)");
  assert.equal(updated.age, 33);

  // Remove
  store.remove(key, "100000002");
  assert.equal(store.read(key).length, 1);
  assert.equal(store.get(key, "100000002"), undefined);
});
