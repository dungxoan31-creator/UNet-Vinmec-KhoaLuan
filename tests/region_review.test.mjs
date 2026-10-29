import test from "node:test";
import assert from "node:assert/strict";
import { buildRegionAssignments } from "../frontend/app/region-review.js";

const components = [{ component_index: 1 }, { component_index: 2 }];
const old = ["region-a", "region-b"];

test("explicitly keeps one prior region and retires an unmatched region", () => {
  const result = buildRegionAssignments(
    components,
    old,
    new Map([[1, "region-a"]]),
    ["region-b"],
  );
  assert.deepEqual(result, {
    assignments: [
      { component_index: 1, previous_region_id: "region-a" },
      { component_index: 2 },
    ],
    retired_region_ids: ["region-b"],
  });
});

test("refuses to silently retire a prior region", () => {
  assert.throws(() => buildRegionAssignments(
    components, old, new Map([[1, "region-a"]]), [],
  ), /kết thúc liên kết/i);
});

test("a prior ID cannot be reused for multiple current components", () => {
  assert.throws(() => buildRegionAssignments(
    components, old, new Map([[1, "region-a"], [2, "region-a"]]), ["region-b"],
  ), /một vùng mới/);
});

test("a region cannot be linked and retired in the same confirmation", () => {
  assert.throws(() => buildRegionAssignments(
    components, old, new Map([[1, "region-a"]]), ["region-a", "region-b"],
  ), /liên kết/);
});

test("a fabricated prior ID is rejected", () => {
  assert.throws(() => buildRegionAssignments(
    components, old, new Map([[1, "region-other"]]), ["region-a", "region-b"],
  ), /không còn hợp lệ/);
});
