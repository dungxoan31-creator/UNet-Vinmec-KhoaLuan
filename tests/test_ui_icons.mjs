import assert from "node:assert/strict";
import test from "node:test";
import { icon } from "../frontend/app/ui.js";

test("ui.js contains edit and trash SVG icons", () => {
  const editSvg = icon("edit");
  const trashSvg = icon("trash");
  assert.match(editSvg, /<svg.*<path/);
  assert.notEqual(editSvg, icon("file"), "edit icon must not fallback to file icon");
  assert.match(trashSvg, /<svg.*<path/);
  assert.notEqual(trashSvg, icon("file"), "trash icon must not fallback to file icon");
});
