import assert from "node:assert/strict";
import test from "node:test";

import { autofillState, viewState, caseState, state } from "../frontend/app/state.js";

test("autofillState records value, provenance source, and confidence", () => {
  autofillState.reset();
  assert.equal(autofillState.get("pid"), "");
  assert.equal(autofillState.provenance("pid").confirmed, false);

  autofillState.set("pid", "VNMC-12345", "dicom", 0.98);
  assert.equal(autofillState.get("pid"), "VNMC-12345");
  const prov = autofillState.provenance("pid");
  assert.equal(prov.source, "dicom");
  assert.equal(prov.confidence, 0.98);
  assert.equal(prov.confirmed, false);

  autofillState.confirm("pid");
  assert.equal(autofillState.provenance("pid").confirmed, true);
});

test("autofillState auto-confirms user edits", () => {
  autofillState.set("patientAge", "34", "user", 1.0);
  const prov = autofillState.provenance("patientAge");
  assert.equal(prov.value, "34");
  assert.equal(prov.source, "user");
  assert.equal(prov.confirmed, true);
});

test("viewState manages zoom, pan, and tool state", () => {
  viewState.reset();
  assert.equal(viewState.zoom, 1.0);
  assert.equal(viewState.panX, 0);
  assert.equal(viewState.panY, 0);

  viewState.zoom = 2.5;
  viewState.panX = 120;
  assert.equal(viewState.zoom, 2.5);

  viewState.reset();
  assert.equal(viewState.zoom, 1.0);
  assert.equal(viewState.panX, 0);
});

test("caseState delegates to root state", () => {
  const dummyCase = { study_id: "test-study-001", images: [] };
  caseState.activeCase = dummyCase;
  assert.equal(state.case, dummyCase);
  assert.equal(caseState.activeCase.study_id, "test-study-001");

  caseState.isDirty = true;
  assert.equal(state.dirty, true);
});
