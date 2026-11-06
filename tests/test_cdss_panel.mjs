import assert from "node:assert/strict";
import test from "node:test";
import {
  bindCdssPanel,
  cdssPanelMarkup,
  updateAIDiagnosisCard,
} from "../frontend/app/cdss-panel.js";

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
    this.confirmation = new FakeElement();
    this.confirmation.checked = false;
  }

  querySelector(selector) {
    if (selector === "#cdssFields") return this.fields;
    if (selector === "#cdssEvaluate") return this.submitButton;
    if (selector === "#cdssConfirm") return this.confirmation;
    return null;
  }

  reportValidity() {
    return true;
  }

  reset() {
    for (const field of Object.values(this.elements)) field.value = "";
  }
}

function createPanel({ canEvaluate = () => true, getContext, signal, requireSavedRegion = false } = {}) {
  const form = new FakeForm();
  const result = new FakeElement();
  const regionHistory = new FakeElement();
  const regionHistoryStatus = new FakeElement();
  const regionHistoryContent = new FakeElement();
  const regionHistoryMore = new FakeElement();
  const root = {
    querySelector(selector) {
      if (selector === "#cdssForm") return form;
      if (selector === "#cdssResult") return result;
      if (selector === "#cdssRegionHistory") return regionHistory;
      if (selector === "#cdssRegionHistoryStatus") return regionHistoryStatus;
      if (selector === "#cdssRegionHistoryContent") return regionHistoryContent;
      if (selector === "#cdssRegionHistoryMore") return regionHistoryMore;
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
    requireSavedRegion,
  });
  return { form, result, panel, getContext: context, regionHistory, regionHistoryStatus, regionHistoryContent, regionHistoryMore };
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
    const call = { url, options, body: options.body ? JSON.parse(options.body) : undefined };
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

test("diagnosis card does not render unsupported model diagnoses", () => {
  const card = new FakeElement();
  const content = new FakeElement();
  content.innerHTML = "";
  const root = {
    querySelector(selector) {
      if (selector === "#aiDiagnosisCard") return card;
      if (selector === "#aiDiagnosisContent") return content;
      return null;
    },
  };

  updateAIDiagnosisCard(root, {
    diagnosis: "Ung thư buồng trứng",
    probability: 0.99,
  });

  assert.match(content.textContent, /chỉ hỗ trợ phân đoạn và đo lường/i);
  assert.doesNotMatch(content.textContent, /Ung thư|99%/i);
  assert.equal(content.innerHTML, "");
});

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
    assert.match(result.textContent, /Đường kính lớn nhất \(mm\)/);
    assert.match(result.textContent, /Số thùy/);
    assert.doesNotMatch(result.textContent, /max_diameter_mm|locules_count/);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("region history is visible, cursor-paged, and rendered as text", async () => {
  const context = {
    studyId: "study-a",
    imageId: "image-left",
    side: "L",
    assignmentRequestId: "assignment-a",
    reviewId: "review-a",
    maskSha256: "a".repeat(64),
    regionId: "region-a",
    reviewRevision: 1,
  };
  const { panel, regionHistory, regionHistoryContent, regionHistoryMore } = createPanel({
    getContext: () => context,
    requireSavedRegion: true,
  });
  const fetch = stubFetch((call) => {
    const isCaliper = call.url.includes("/calipers?");
    const hasCursor = call.url.includes("cursor=");
    if (isCaliper && !hasCursor) return {
      current: true,
      measurements: {},
      history: [{ request_id: "caliper-new", label: "D1", measurement_revision: 2, diameter_mm: 4.5,
        current: true, created_at: "2026-10-29T10:00:00" }],
      history_next_cursor: "caliper-cursor",
    };
    if (isCaliper) return {
      current: true,
      measurements: {},
      history: [{ request_id: "caliper-old", label: "D1", measurement_revision: 1, diameter_mm: 4.2,
        current: false, created_at: "2026-10-29T09:00:00" }],
      history_next_cursor: null,
    };
    if (!hasCursor) return {
      current: true,
      latest_revision: 3,
      latest: null,
      history: [{ request_id: "assessment-new", assessment_revision: 3, result: { status: "INSUFFICIENT_DATA" },
        current: true, created_at: "2026-10-29T10:01:00" }],
      history_next_cursor: "assessment-cursor",
    };
    return {
      current: true,
      latest_revision: 3,
      latest: null,
      history: [{ request_id: "assessment-old", assessment_revision: 2, result: { status: "<script>" },
        current: false, created_at: "<script>" }],
      history_next_cursor: null,
    };
  });
  try {
    panel.setRegionContext(context);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(regionHistory.hidden, false);
    assert.equal(regionHistoryMore.hidden, false);
    assert.match(regionHistoryContent.textContent, /4\.500 mm/);
    assert.match(regionHistoryContent.textContent, /Chưa đủ dữ liệu/);

    await regionHistoryMore.dispatch("click");
    assert.equal(fetch.calls.length, 4);
    assert.ok(fetch.calls.some((call) => call.url.includes("cursor=caliper-cursor")));
    assert.ok(fetch.calls.some((call) => call.url.includes("cursor=assessment-cursor")));
    assert.match(regionHistoryContent.textContent, /revision 1 · 4\.200 mm · lịch sử \/ stale/);
    assert.match(regionHistoryContent.textContent, /<script>/);
    assert.equal(regionHistoryMore.hidden, true);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("late history responses from a previously selected region never replace the current region", async () => {
  const regionA = {
    studyId: "study-a", imageId: "image-left", side: "L",
    assignmentRequestId: "assignment-a", reviewId: "review-a", maskSha256: "a".repeat(64),
    regionId: "region-a", reviewRevision: 1,
  };
  const regionB = {
    ...regionA,
    assignmentRequestId: "assignment-b", reviewId: "review-b", maskSha256: "b".repeat(64),
    regionId: "region-b", reviewRevision: 2,
  };
  const { panel, regionHistoryContent } = createPanel({ requireSavedRegion: true });
  const resolvers = new Map();
  const fetch = stubFetch((call) => new Promise((resolve) => resolvers.set(call.url, resolve)));
  const flush = () => new Promise((resolve) => setImmediate(resolve));
  const calipers = (requestId, diameter) => ({
    current: true,
    measurements: {},
    history: [{ request_id: requestId, label: "D1", measurement_revision: 1, diameter_mm: diameter, current: true }],
    history_next_cursor: null,
  });
  const assessments = (requestId, revision) => ({
    current: true,
    latest_revision: revision,
    latest: null,
    history: [{ request_id: requestId, assessment_revision: revision, result: { status: "INSUFFICIENT_DATA" }, current: true }],
    history_next_cursor: null,
  });

  try {
    panel.setRegionContext(regionA);
    await flush();
    assert.equal(fetch.calls.length, 2);
    panel.setRegionContext(regionB);
    await flush();
    assert.equal(fetch.calls.length, 4);

    for (const call of fetch.calls.slice(2)) {
      const isCaliper = call.url.includes("/calipers?");
      resolvers.get(call.url)(isCaliper ? calipers("region-b-caliper", 2.2) : assessments("region-b-assessment", 2));
    }
    await flush();
    assert.match(regionHistoryContent.textContent, /2\.200 mm/);
    assert.match(regionHistoryContent.textContent, /Revision 2/);

    for (const call of fetch.calls.slice(0, 2)) {
      const isCaliper = call.url.includes("/calipers?");
      resolvers.get(call.url)(isCaliper ? calipers("region-a-caliper", 9.9) : assessments("region-a-assessment", 99));
    }
    await flush();
    assert.match(regionHistoryContent.textContent, /2\.200 mm/);
    assert.match(regionHistoryContent.textContent, /Revision 2/);
    assert.doesNotMatch(regionHistoryContent.textContent, /9\.900 mm|Revision 99/);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});

test("stale saved assessment requires region reload before a new revision is submitted", async () => {
  const context = {
    studyId: "study-a",
    imageId: "image-left",
    side: "L",
    leaseToken: "lease-a",
    pageInstanceId: "page-a",
  };
  const region = {
    studyId: context.studyId,
    imageId: context.imageId,
    assignmentRequestId: "assignment-a",
    reviewId: "review-a",
    maskSha256: "a".repeat(64),
    regionId: "region-a",
    reviewRevision: 1,
  };
  const { form, result, panel } = createPanel({
    getContext: () => context,
    requireSavedRegion: true,
  });
  let assessmentReads = 0;
  const fetch = stubFetch((call) => {
    if (call.options.method === "POST") {
      if (call.body.expected_assessment_revision === 0)
        return { current: false, assessment_revision: 1, result: { status: "INSUFFICIENT_DATA" } };
      return { current: true, assessment_revision: 2, result: cdssResponse() };
    }
    if (call.url.includes("/calipers?"))
      return { current: true, measurements: {}, history: [], history_next_cursor: null };
    assessmentReads += 1;
    return {
      current: true,
      latest_revision: assessmentReads === 1 ? 0 : 1,
      latest: null,
      history: [],
      history_next_cursor: null,
    };
  });
  try {
    panel.setRegionContext(region);
    await new Promise((resolve) => setTimeout(resolve, 0));
    form.confirmation.checked = true;
    await form.dispatch("submit");

    const stalePost = fetch.calls.find((call) => call.options.method === "POST");
    assert.ok(stalePost);
    assert.equal(stalePost.body.expected_assessment_revision, 0);
    assert.equal(form.confirmation.checked, false);
    assert.equal(form.submitButton.disabled, true);
    assert.equal(result.dataset.status, "STALE");
    assert.match(result.textContent, /chọn lại vùng/i);

    panel.setRegionContext(region);
    await new Promise((resolve) => setTimeout(resolve, 0));
    form.confirmation.checked = true;
    await form.dispatch("submit");

    const posts = fetch.calls.filter((call) => call.options.method === "POST");
    assert.equal(posts.length, 2);
    assert.notEqual(posts[1].body.request_id, stalePost.body.request_id);
    assert.equal(posts[1].body.expected_assessment_revision, 1);
    assert.equal(result.dataset.status, "INSUFFICIENT_DATA");
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
    assert.match(result.textContent, /Đường kính lớn nhất \(mm\)/);
    assert.match(result.textContent, /Số thùy/);
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

test("cancelling a pending CDSS request restores its idle button and editability", async () => {
  let resolveResponse;
  const { form, result, panel } = createPanel();
  const fetch = stubFetch(() => new Promise((resolve) => { resolveResponse = resolve; }));
  try {
    const submission = form.dispatch("submit");
    assert.equal(form.submitButton.textContent, "Đang đối chiếu…");
    panel.resetForSide();
    assert.equal(form.submitButton.textContent, "Đối chiếu quy tắc");
    assert.equal(form.submitButton.disabled, false);
    assert.equal(form.fields.disabled, false);
    resolveResponse(cdssResponse({ status: "RULE_MATCHED", category: "O-RADS 2" }));
    await submission;
    assert.equal(result.dataset.status, "NOT_EVALUATED");
    assert.doesNotMatch(result.textContent, /O-RADS 2/);
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
    assert.match(result.textContent, /Mẫu hình chưa được quy tắc hỗ trợ/);
    assert.doesNotMatch(result.textContent, /UNSUPPORTED_PATTERN/);

    nextResponse = cdssResponse({ status: "RULE_MATCHED", category: "O-RADS 2" });
    await form.dispatch("input");
    await form.dispatch("submit");
    assert.match(result.textContent, /O-RADS 2/);
    assert.match(result.textContent, /cần bác sĩ xác nhận/i);
    assert.match(result.textContent, /example\.test\/source/);
    assert.doesNotMatch(result.textContent, /SYNTHETIC_MANAGEMENT_SHOULD_NOT_RENDER/);
  } finally {
    panel.destroy();
    fetch.restore();
  }
});
