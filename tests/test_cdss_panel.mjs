import assert from "node:assert/strict";
import test from "node:test";
import { bindCdssPanel, cdssPanelMarkup } from "../frontend/app/cdss-panel.js";

const fieldNames = [
  "assessment_source",
  "modality",
  "ultrasound_exam_complete",
  "max_diameter_mm",
  "locules_count",
  "has_solid_component",
  "papillary_projections_count",
  "fluid_echogenicity",
  "acoustic_shadowing",
  "wall_irregular",
  "color_score",
  "has_ascites",
  "has_peritoneal_nodules",
  "is_premenopausal",
  "is_persistent_adnexal_mass",
  "surgery_indicated",
  "b1_unilocular_cyst",
  "b2_solid_component_lt_7mm",
  "b3_acoustic_shadows",
  "b4_smooth_multilocular_lt_100mm",
  "b5_no_detectable_blood_flow",
  "m1_irregular_solid_tumor",
  "m2_ascites",
  "m3_four_or_more_papillary_projections",
  "m4_irregular_multilocular_solid_ge_100mm",
  "m5_very_strong_color_doppler",
];

class FakeElement {
  constructor(value = "") {
    this.value = value;
    this.disabled = false;
    this.hidden = false;
    this.dataset = {};
    this.textContent = "";
    this.attributes = {};
    this.listeners = new Map();
  }

  addEventListener(type, callback, options = {}) {
    if (options.signal?.aborted) return;
    const callbacks = this.listeners.get(type) ?? new Set();
    callbacks.add(callback);
    this.listeners.set(type, callbacks);
    options.signal?.addEventListener(
      "abort",
      () => callbacks.delete(callback),
      { once: true },
    );
  }

  async dispatch(type, target = this) {
    const event = {
      type,
      target,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
    };
    for (const callback of this.listeners.get(type) ?? []) await callback(event);
    return event;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
}

class FakeForm extends FakeElement {
  constructor() {
    super();
    this.elements = Object.fromEntries(
      fieldNames.map((name) => [name, new FakeElement()]),
    );
    this.fields = new FakeElement();
    this.submitButton = new FakeElement();
  }

  querySelector(selector) {
    if (selector === "#cdssFields") return this.fields;
    if (selector === "#cdssEvaluate") return this.submitButton;
    return null;
  }

  reportValidity() {
    return true;
  }

  reset() {
    for (const field of Object.values(this.elements)) field.value = "";
  }
}

function createPanel({ canEvaluate = () => true, getContext, signal } = {}) {
  const form = new FakeForm();
  const result = new FakeElement();
  const root = {
    querySelector(selector) {
      if (selector === "#cdssForm") return form;
      if (selector === "#cdssResult") return result;
      return null;
    },
  };
  const context = getContext ?? (() => ({
    studyId: "study-a",
    imageId: "image-left",
    side: "L",
  }));
  const panel = bindCdssPanel(root, {
    canEvaluate,
    getContext: context,
    signal,
  });
  return { form, result, panel, getContext: context };
}

function cdssResponse({ status = "INSUFFICIENT_DATA", category = null } = {}) {
  return {
    status,
    orads_stratification: {
      category,
      reason: "Cần thêm mô tả do bác sĩ nhập.",
      missing_fields: ["max_diameter_mm", "locules_count"],
      clinical_management: "SYNTHETIC_MANAGEMENT_SHOULD_NOT_RENDER",
      requires_clinician_confirmation: true,
    },
    iota_evaluation: {
      rule_verdict: "NOT_EVALUATED",
      missing_fields: [],
      interpretation: "Rule output only; not a diagnosis.",
    },
    citations: [{ title: "ACR O-RADS US v2022", url: "https://example.test/source" }],
  };
}

function stubFetch(responseOrFactory) {
  const previousFetch = globalThis.fetch;
  const previousNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { onLine: true },
  });
  const calls = [];
  globalThis.fetch = async (url, options) => {
    const call = { url, options, body: JSON.parse(options.body) };
    calls.push(call);
    const response = typeof responseOrFactory === "function"
      ? await responseOrFactory(call, calls.length - 1)
      : responseOrFactory;
    return {
      status: 200,
      ok: true,
      headers: { get: () => null },
      json: async () => response,
    };
  };
  return {
    calls,
    restore() {
      globalThis.fetch = previousFetch;
      if (previousNavigator)
        Object.defineProperty(globalThis, "navigator", previousNavigator);
      else delete globalThis.navigator;
    },
  };
}

test("test_cdss_panel_starts_unanswered_and_sends_no_defaults", async () => {
  const markup = cdssPanelMarkup(false);
  assert.match(markup, /id="cdssForm"/);
  assert.match(markup, /<select[^>]*name="ultrasound_exam_complete"[^>]*>[\s\S]*?<option value=""/);
  const selects = [...markup.matchAll(/<select\b[^>]*>([\s\S]*?)<\/select>/g)];
  assert.ok(selects.length >= fieldNames.length - 3, "the full descriptor set is rendered");
  assert.ok(selects.every(([, contents]) => /^\s*<option value=""/.test(contents)),
    "every select starts on its unanswered option");
  assert.doesNotMatch(markup, /<input\b[^>]*\bvalue="[^"]+"/,
    "numeric descriptors do not start with prefilled values");
  const { form, result, panel } = createPanel();
  const fetch = stubFetch(cdssResponse());
  try {
    assert.ok(fieldNames.every((name) => form.elements[name].value === ""));
    await form.dispatch("submit");
    assert.equal(fetch.calls.length, 1);
    assert.equal(fetch.calls[0].url, "/api/v1/cdss/evaluate");
    assert.equal(fetch.calls[0].options.method, "POST");
    assert.deepEqual(fetch.calls[0].body.vision_findings, {});
    assert.equal("patient_context" in fetch.calls[0].body, false);
    assert.match(result.textContent, /max_diameter_mm/);
    assert.match(result.textContent, /locules_count/);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("test_partial_inputs_keep_missing_fields_visible", async () => {
  const { form, result, panel } = createPanel();
  const fetch = stubFetch(cdssResponse());
  try {
    form.elements.assessment_source.value = "clinician";
    form.elements.modality.value = "ultrasound_2d";
    form.elements.ultrasound_exam_complete.value = "false";
    form.elements.max_diameter_mm.value = "35";
    form.elements.is_premenopausal.value = "false";
    await form.dispatch("submit");
    const body = fetch.calls[0].body;
    assert.deepEqual(body.vision_findings, {
      assessment_source: "clinician",
      modality: "ultrasound_2d",
      ultrasound_exam_complete: false,
      max_diameter_mm: 35,
    });
    assert.deepEqual(body.patient_context, { is_premenopausal: false });
    assert.equal("locules_count" in body.vision_findings, false);
    assert.equal("has_solid_component" in body.vision_findings, false);
    assert.match(result.textContent, /max_diameter_mm/);
    assert.match(result.textContent, /locules_count/);
    assert.doesNotMatch(result.textContent, /O-RADS 2/);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("test_non_integer_counts_are_not_serialized", async () => {
  const { form, panel } = createPanel();
  const fetch = stubFetch(cdssResponse());
  try {
    form.elements.assessment_source.value = "clinician";
    form.elements.modality.value = "ultrasound_2d";
    form.elements.locules_count.value = "1.5";
    form.elements.papillary_projections_count.value = "0.5";
    await form.dispatch("submit");
    assert.equal("locules_count" in fetch.calls[0].body.vision_findings, false);
    assert.equal("papillary_projections_count" in fetch.calls[0].body.vision_findings, false);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("test_side_change_discards_stale_response", async () => {
  let context = { studyId: "study-a", imageId: "image-left", side: "L" };
  let resolveResponse;
  const { form, result, panel } = createPanel({ getContext: () => context });
  const fetch = stubFetch(() => new Promise((resolve) => { resolveResponse = resolve; }));
  try {
    const submission = form.dispatch("submit");
    context = { studyId: "study-a", imageId: "image-right", side: "R" };
    panel.resetForSide();
    resolveResponse(cdssResponse({ status: "RULE_MATCHED", category: "O-RADS 2" }));
    await submission;
    assert.doesNotMatch(result.textContent, /O-RADS 2/);
    assert.equal(result.dataset.status, "NOT_EVALUATED");
    assert.ok(fieldNames.every((name) => form.elements[name].value === ""));
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("test_route_abort_discards_response", async () => {
  const route = new AbortController();
  let resolveResponse;
  const { form, result, panel } = createPanel({ signal: route.signal });
  const fetch = stubFetch(() => new Promise((resolve) => { resolveResponse = resolve; }));
  try {
    const submission = form.dispatch("submit");
    route.abort();
    resolveResponse(cdssResponse({ status: "RULE_MATCHED", category: "O-RADS 2" }));
    await submission;
    assert.doesNotMatch(result.textContent, /O-RADS 2/);
    assert.notEqual(result.dataset.status, "RULE_MATCHED");
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("test_lease_loss_discards_response", async () => {
  let resolveResponse;
  const { form, result, panel } = createPanel();
  const fetch = stubFetch(() => new Promise((resolve) => { resolveResponse = resolve; }));
  try {
    const submission = form.dispatch("submit");
    panel.setEditable(false);
    resolveResponse(cdssResponse({ status: "RULE_MATCHED", category: "O-RADS 2" }));
    await submission;
    assert.equal(form.fields.disabled, true);
    assert.equal(form.submitButton.disabled, true);
    assert.doesNotMatch(result.textContent, /O-RADS 2/);
    assert.doesNotMatch(result.textContent, /SYNTHETIC_MANAGEMENT_SHOULD_NOT_RENDER/);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("test_only_rule_matched_displays_ruo_category", async () => {
  let nextResponse = cdssResponse({ status: "UNSUPPORTED_PATTERN", category: "O-RADS 2" });
  const { form, result, panel } = createPanel();
  const fetch = stubFetch(() => nextResponse);
  try {
    await form.dispatch("submit");
    assert.doesNotMatch(result.textContent, /O-RADS 2/);
    assert.match(result.textContent, /UNSUPPORTED_PATTERN/);

    nextResponse = cdssResponse({ status: "RULE_MATCHED", category: "O-RADS 2" });
    await form.dispatch("input");
    await form.dispatch("submit");
    assert.match(result.textContent, /O-RADS 2/);
    assert.match(result.textContent, /RUO/i);
    assert.match(result.textContent, /example\.test\/source/);
    assert.doesNotMatch(result.textContent, /SYNTHETIC_MANAGEMENT_SHOULD_NOT_RENDER/);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});
