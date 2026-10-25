import assert from "node:assert/strict";
import test from "node:test";

const timers = [];
const toastHost = {
  children: [],
  append(node) {
    this.children.push(node);
  },
};

globalThis.document = {
  createElement() {
    return {
      remove() {
        this.removed = true;
      },
    };
  },
  querySelector(selector) {
    assert.equal(selector, "#toasts");
    return toastHost;
  },
};
globalThis.setTimeout = (callback, delay) => {
  timers.push({ callback, delay });
  return timers.length;
};

const { toast } = await import("../frontend/app/ui.js");

test("successful status toasts disappear after 1.2 seconds", () => {
  toast("Đã lưu ca");

  const node = toastHost.children.at(-1);
  const timer = timers.at(-1);
  assert.equal(node.role, "status");
  assert.equal(timer.delay, 1200);
  timer.callback();
  assert.equal(node.removed, true);
});

test("error toasts remain visible for six seconds", () => {
  toast("Không thể lưu ca", true);

  const node = toastHost.children.at(-1);
  const timer = timers.at(-1);
  assert.equal(node.role, "alert");
  assert.equal(timer.delay, 6000);
  timer.callback();
  assert.equal(node.removed, true);
});
