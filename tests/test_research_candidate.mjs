import assert from "node:assert/strict";
import test from "node:test";

import { createTracker } from "../frontend/app/hitl-tracker.js";
import { encode } from "../frontend/app/coordinates.js";
import {
  bindResearchCandidate,
  researchCandidateMarkup,
} from "../frontend/app/research-candidate.js";

const MASK_SIZE = 512 * 512;
const PARAMETER_NAMES = [
  "min_component_area",
  "closing_kernel_size",
  "fill_holes",
  "smoothing_kernel_size",
];

class FakeElement {
  constructor(value = "") {
    this.value = value;
    this.disabled = false;
    this.hidden = false;
    this.textContent = "";
    this.dataset = {};
    this.attributes = {};
    this.listeners = new Map();
    this.parentElement = null;
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

  async dispatch(type) {
    const event = {
      type,
      target: this,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
    };
    for (const callback of this.listeners.get(type) ?? []) await callback(event);
    if (this.parentElement) {
      event.currentTarget = this.parentElement;
      for (const callback of this.parentElement.listeners.get(type) ?? [])
        await callback(event);
    }
    return event;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
}

class FakeCanvas extends FakeElement {
  constructor() {
    super();
    this.frames = [];
    this.context = {
      createImageData: (width, height) => ({
        width,
        height,
        data: new Uint8ClampedArray(width * height * 4),
      }),
      putImageData: (frame) => this.frames.push(frame),
    };
  }

  getContext() {
    return this.context;
  }
}

class FakeForm extends FakeElement {
  constructor() {
    super();
    this.elements = Object.fromEntries(
      PARAMETER_NAMES.map((name) => [name, new FakeElement()]),
    );
    for (const element of Object.values(this.elements)) element.parentElement = this;
    this.fields = new FakeElement();
    this.previewButton = new FakeElement();
  }

  querySelector(selector) {
    if (selector === "#researchCandidateFields") return this.fields;
    if (selector === "#researchCandidatePreview") return this.previewButton;
    return null;
  }

  reportValidity() {
    return true;
  }

  reset() {
    for (const control of Object.values(this.elements)) control.value = "";
  }
}

function rectangle(x0, y0, x1, y1) {
  const mask = new Uint8Array(MASK_SIZE);
  for (let y = y0; y < y1; y++)
    for (let x = x0; x < x1; x++) mask[y * 512 + x] = 1;
  return mask;
}

function responseFor(baseline, candidate = baseline) {
  return {
    success: true,
    baseline_mask_rle: encode(baseline),
    candidate_mask_rle: encode(candidate),
    candidate_parameters: {
      min_component_area: 0,
      closing_kernel_size: 0,
      fill_holes: false,
      smoothing_kernel_size: null,
    },
    provenance: {
      prediction_id: "prediction-left",
      model_version: "model-test-v1",
      checkpoint_sha256: null,
      algorithm: "explicit_morphology_candidate",
      algorithm_version: "1.0.0",
    },
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
    const call = {
      url,
      options,
      body: JSON.parse(options.body),
    };
    calls.push(call);
    const result = typeof responseOrFactory === "function"
      ? await responseOrFactory(call, calls.length - 1)
      : responseOrFactory;
    if (result instanceof Error) throw result;
    return {
      status: result?.status ?? 200,
      ok: result?.ok ?? true,
      headers: { get: () => null },
      json: async () => result?.body ?? result,
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

function createHarness({
  baseline = rectangle(100, 100, 120, 120),
  canEdit = () => true,
  signal,
  onApply = () => true,
} = {}) {
  const currentMask = baseline.slice();
  const context = {
    studyId: "study-a",
    imageId: "image-left",
    predictionId: "prediction-left",
    side: "L",
    currentMask,
    aiMask: baseline.slice(),
  };
  const form = new FakeForm();
  const status = new FakeElement();
  const applyButton = new FakeElement();
  const baselineCanvas = new FakeCanvas();
  const candidateCanvas = new FakeCanvas();
  const elements = new Map([
    ["#researchCandidateForm", form],
    ["#researchCandidateStatus", status],
    ["#researchCandidateApply", applyButton],
    ["#researchCandidateBaseline", baselineCanvas],
    ["#researchCandidateCandidate", candidateCanvas],
  ]);
  const root = new FakeElement();
  root.querySelector = (selector) => elements.get(selector) ?? null;
  root.dispatchEvent = async (event) => root.dispatch(event.type);
  const panel = bindResearchCandidate(root, {
    getContext: () => context,
    canEdit,
    signal,
    onApply,
  });
  return {
    root,
    form,
    context,
    status,
    applyButton,
    baselineCanvas,
    candidateCanvas,
    panel,
  };
}

async function selectAllParameters(form) {
  form.elements.min_component_area.value = "0";
  form.elements.closing_kernel_size.value = "0";
  form.elements.fill_holes.value = "false";
  form.elements.smoothing_kernel_size.value = "none";
  for (const name of PARAMETER_NAMES) await form.elements[name].dispatch("change");
}

test("test_parameters_start_unanswered_and_gate_generation", async () => {
  const markup = researchCandidateMarkup();
  assert.match(markup, /id="researchCandidateForm"/);
  assert.equal(
    [...markup.matchAll(/<select\b[^>]*>/g)].length,
    PARAMETER_NAMES.length,
  );
  const optionLists = [...markup.matchAll(/<select\b[^>]*>([\s\S]*?)<\/select>/g)];
  assert.ok(optionLists.every(([, options]) => /^\s*<option value=""/.test(options)));
  const harness = createHarness();
  const fetch = stubFetch(responseFor(harness.context.aiMask));
  try {
    assert.ok(PARAMETER_NAMES.every((name) => harness.form.elements[name].value === ""));
    assert.equal(harness.form.previewButton.disabled, true);
    await harness.form.dispatch("submit");
    assert.equal(fetch.calls.length, 0);
    await selectAllParameters(harness.form);
    assert.equal(harness.form.previewButton.disabled, false);
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_generation_only_previews_candidate", async () => {
  const harness = createHarness();
  const candidate = harness.context.aiMask.slice();
  candidate[150 * 512 + 150] = 1;
  const fetch = stubFetch(responseFor(harness.context.aiMask, candidate));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    assert.equal(fetch.calls.length, 1);
    assert.equal(fetch.calls[0].url, "/api/v1/segment/candidate");
    assert.deepEqual(fetch.calls[0].body, {
      study_id: "study-a",
      image_id: "image-left",
      prediction_id: "prediction-left",
      min_component_area: 0,
      closing_kernel_size: 0,
      fill_holes: false,
      smoothing_kernel_size: null,
    });
    assert.equal("baseline_mask_rle" in fetch.calls[0].body, false);
    assert.equal("patient_id" in fetch.calls[0].body, false);
    assert.ok(harness.candidateCanvas.frames.length > 0, "candidate mask is previewed read-only");
    assert.equal(harness.candidateCanvas.frames.at(-1).data[(150 * 512 + 150) * 4], 255);
    assert.equal(harness.context.currentMask[150 * 512 + 150], 0);
    assert.equal(harness.applyButton.disabled, false);
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_candidate_request_failure_keeps_baseline_usable", async () => {
  const harness = createHarness();
  const baselineBytes = harness.context.currentMask.slice();
  const fetch = stubFetch({ status: 503, ok: false, body: { detail: "temporarily unavailable" } });
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    assert.equal(harness.status.dataset.status, "ERROR");
    assert.equal(harness.applyButton.disabled, true);
    assert.deepEqual(harness.context.currentMask, baselineBytes);
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_apply_is_disabled_after_manual_edits", async () => {
  const harness = createHarness();
  const candidate = harness.context.aiMask.slice();
  candidate[150 * 512 + 150] = 1;
  const fetch = stubFetch(responseFor(harness.context.aiMask, candidate));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    assert.equal(harness.applyButton.disabled, false);
    harness.context.currentMask[0] = 1;
    await harness.root.dispatch("ova:mask-changed");
    assert.equal(harness.applyButton.disabled, true);
    await harness.applyButton.dispatch("click");
    assert.equal(harness.context.currentMask[0], 1);
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_readonly_or_lost_lease_disables_apply", async () => {
  let editable = false;
  const harness = createHarness({ canEdit: () => editable });
  const candidate = harness.context.aiMask.slice();
  candidate[150 * 512 + 150] = 1;
  const fetch = stubFetch(responseFor(harness.context.aiMask, candidate));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    assert.equal(harness.applyButton.disabled, true, "read-only view cannot apply");
    editable = true;
    await harness.root.dispatch("ova:lease-restored");
    assert.equal(harness.applyButton.disabled, false);
    editable = false;
    await harness.root.dispatch("ova:lease-lost");
    assert.equal(harness.applyButton.disabled, true, "lease loss removes apply capability");
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_empty_candidate_is_preview_only", async () => {
  const harness = createHarness();
  const fetch = stubFetch(responseFor(harness.context.aiMask, new Uint8Array(MASK_SIZE)));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    assert.ok(harness.candidateCanvas.frames.length > 0);
    assert.equal(harness.applyButton.disabled, true);
    assert.match(harness.status.textContent, /chỉ xem|preview-only/i);
    assert.ok(harness.context.currentMask.some((value) => value === 1));
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_apply_is_one_undoable_edit", async () => {
  const history = [];
  let applyCount = 0;
  let harness;
  harness = createHarness({
    onApply: ({ mask }) => {
      history.push(harness.context.currentMask.slice());
      harness.context.currentMask.set(mask);
      applyCount += 1;
      return true;
    },
  });
  const candidate = harness.context.aiMask.slice();
  candidate[110 * 512 + 110] = 0;
  const fetch = stubFetch(responseFor(harness.context.aiMask, candidate));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    await harness.applyButton.dispatch("click");
    assert.equal(applyCount, 1);
    assert.deepEqual(harness.context.currentMask, candidate);
    assert.equal(history.length, 1);
    harness.context.currentMask.set(history.pop());
    assert.deepEqual(harness.context.currentMask, harness.context.aiMask);
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_undo_redo_restores_exact_mask_bytes", async () => {
  const history = [];
  const redo = [];
  let harness;
  harness = createHarness({
    onApply: ({ mask }) => {
      history.push(harness.context.currentMask.slice());
      harness.context.currentMask.set(mask);
      return true;
    },
  });
  const candidate = harness.context.aiMask.slice();
  candidate[100 * 512 + 100] = 0;
  const before = encode(harness.context.currentMask);
  const fetch = stubFetch(responseFor(harness.context.aiMask, candidate));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    await harness.applyButton.dispatch("click");
    redo.push(harness.context.currentMask.slice());
    harness.context.currentMask.set(history.pop());
    assert.deepEqual(encode(harness.context.currentMask), before);
    harness.context.currentMask.set(redo.pop());
    assert.deepEqual(encode(harness.context.currentMask), encode(candidate));
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_side_or_route_change_invalidates_candidate", async () => {
  const harness = createHarness();
  const candidate = harness.context.aiMask.slice();
  candidate[150 * 512 + 150] = 1;
  const fetch = stubFetch(responseFor(harness.context.aiMask, candidate));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    assert.equal(harness.applyButton.disabled, false);
    harness.context.side = "R";
    harness.context.imageId = "image-right";
    harness.context.predictionId = "prediction-right";
    harness.panel.resetForSide();
    assert.equal(harness.applyButton.disabled, true);
    assert.ok(PARAMETER_NAMES.every((name) => harness.form.elements[name].value === ""));
    assert.equal(
      harness.candidateCanvas.frames.at(-1).data[(150 * 512 + 150) * 4],
      20,
      "stale candidate pixels are cleared when the side changes",
    );

    const route = new AbortController();
    const routeHarness = createHarness({ signal: route.signal });
    const routeCandidate = routeHarness.context.aiMask.slice();
    routeCandidate[150 * 512 + 150] = 1;
    const routeFetch = stubFetch(responseFor(routeHarness.context.aiMask, routeCandidate));
    await selectAllParameters(routeHarness.form);
    await routeHarness.form.dispatch("submit");
    route.abort();
    assert.equal(routeHarness.applyButton.disabled, true);
    assert.ok(routeHarness.panel);
    routeHarness.panel.destroy();
    routeFetch.restore();
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_apply_does_not_write_until_review_save", async () => {
  let harness;
  harness = createHarness({
    onApply: ({ mask }) => {
      harness.context.currentMask.set(mask);
      return true;
    },
  });
  const candidate = harness.context.aiMask.slice();
  candidate[110 * 512 + 110] = 0;
  const fetch = stubFetch(responseFor(harness.context.aiMask, candidate));
  try {
    await selectAllParameters(harness.form);
    await harness.form.dispatch("submit");
    await harness.applyButton.dispatch("click");
    assert.equal(fetch.calls.length, 1);
    assert.equal(fetch.calls[0].url, "/api/v1/segment/candidate");
    assert.deepEqual(harness.context.currentMask, candidate);
  } finally {
    harness.panel.destroy();
    fetch.restore();
  }
});

test("test_candidate_apply_telemetry_is_allowlisted", async () => {
  const tracker = createTracker({
    now: () => 100,
    utc: () => "2026-10-25T12:00:00.000Z",
    request: async () => ({ id: "session-1" }),
    storage: null,
  });
  await tracker.startSession("study-a");
  tracker.startTask("image-left", "prediction-left");
  tracker.startStroke("image-left");
  tracker.commitEdit("image-left", {
    tool: "candidate_apply",
    changed_pixels: 17,
    patient_name: "must-not-be-recorded",
  });
  const event = tracker.getTaskEvents("image-left").find((item) => item.event_type === "EDIT_COMMITTED");
  assert.deepEqual(event.payload, { tool: "candidate_apply", changed_pixels: 17 });
  assert.equal(JSON.stringify(event).includes("must-not-be-recorded"), false);
  assert.equal(JSON.stringify(event).includes("image-left"), true);
  tracker.reset();
});

test("test_candidate_apply_telemetry_keeps_bounded_transform_provenance", async () => {
  const tracker = createTracker({
    now: () => 100,
    utc: () => "2026-10-25T12:00:00.000Z",
    request: async () => ({ id: "session-1" }),
    storage: null,
  });
  await tracker.startSession("study-a");
  tracker.startTask("image-left", "prediction-left");
  tracker.startStroke("image-left");
  tracker.commitEdit("image-left", {
    tool: "candidate_apply",
    changed_pixels: 17,
    candidate_parameters: {
      min_component_area: 12,
      closing_kernel_size: 3,
      fill_holes: true,
      smoothing_kernel_size: null,
    },
    candidate_provenance: {
      prediction_id: "prediction-left",
      model_version: "synthetic-model-v1",
      checkpoint_sha256: "a".repeat(64),
      algorithm: "explicit_morphology_candidate",
      algorithm_version: "1.0.0",
      patient_name: "must-not-be-recorded",
    },
    patient_name: "must-not-be-recorded",
  });
  const event = tracker.getTaskEvents("image-left").find((item) => item.event_type === "EDIT_COMMITTED");
  assert.deepEqual(event.payload, {
    tool: "candidate_apply",
    changed_pixels: 17,
    candidate_algorithm: "explicit_morphology_candidate",
    candidate_algorithm_version: "1.0.0",
    candidate_prediction_id: "prediction-left",
    candidate_model_version: "synthetic-model-v1",
    candidate_checkpoint_sha256: "a".repeat(64),
    candidate_min_component_area: 12,
    candidate_closing_kernel_size: 3,
    candidate_fill_holes: true,
    candidate_smoothing_kernel_size: null,
  });
  assert.equal(JSON.stringify(event).includes("must-not-be-recorded"), false);
  tracker.reset();
});

test("test_candidate_apply_provenance_survives_outbox_reload_and_replay", async () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
  const source = createTracker({
    now: () => 100,
    utc: () => "2026-10-25T12:00:00.000Z",
    request: async () => ({ id: "session-1" }),
    storage,
  });
  await source.startSession("study-a");
  source.startTask("image-left", "prediction-left");
  source.startStroke("image-left");
  source.commitEdit("image-left", {
    tool: "candidate_apply",
    changed_pixels: 1,
    candidate_parameters: {
      min_component_area: 12,
      closing_kernel_size: 3,
      fill_holes: true,
      smoothing_kernel_size: null,
    },
    candidate_provenance: {
      prediction_id: "prediction-left",
      model_version: "synthetic-model-v1",
      checkpoint_sha256: "b".repeat(64),
      algorithm: "explicit_morphology_candidate",
      algorithm_version: "1.0.0",
    },
  });
  source.reset();

  const replayed = [];
  const restarted = createTracker({
    now: () => 200,
    utc: () => "2026-10-25T12:01:00.000Z",
    request: async (_path, { body }) => {
      replayed.push(...body.events);
      return { accepted: true };
    },
    storage,
  });
  await restarted.flushPendingEvents("study-a", {}, null);
  const candidateEvent = replayed.find((event) =>
    event.event_type === "EDIT_COMMITTED" && event.payload?.tool === "candidate_apply",
  );
  assert.deepEqual(candidateEvent?.payload, {
    tool: "candidate_apply",
    changed_pixels: 1,
    candidate_algorithm: "explicit_morphology_candidate",
    candidate_algorithm_version: "1.0.0",
    candidate_prediction_id: "prediction-left",
    candidate_model_version: "synthetic-model-v1",
    candidate_checkpoint_sha256: "b".repeat(64),
    candidate_min_component_area: 12,
    candidate_closing_kernel_size: 3,
    candidate_fill_holes: true,
    candidate_smoothing_kernel_size: null,
  });
  assert.equal(values.has("ova.hitl.outbox.v1"), false, "successful replay clears the pending outbox");
  restarted.reset();
});

test("test_candidate_telemetry_rejects_zero_smoothing_kernel", async () => {
  const tracker = createTracker({
    now: () => 100,
    utc: () => "2026-10-25T12:00:00.000Z",
    request: async () => ({ id: "session-1" }),
    storage: null,
  });
  await tracker.startSession("study-a");
  tracker.startTask("image-left", "prediction-left");
  tracker.startStroke("image-left");
  tracker.commitEdit("image-left", {
    tool: "candidate_apply",
    changed_pixels: 1,
    candidate_parameters: {
      min_component_area: 0,
      closing_kernel_size: 0,
      fill_holes: false,
      smoothing_kernel_size: 0,
    },
    candidate_provenance: {
      prediction_id: "prediction-left",
      model_version: "synthetic-model-v1",
      checkpoint_sha256: null,
      algorithm: "explicit_morphology_candidate",
      algorithm_version: "1.0.0",
    },
  });
  const event = tracker.getTaskEvents("image-left").find((item) => item.event_type === "EDIT_COMMITTED");
  assert.deepEqual(event.payload, { tool: "candidate_apply", changed_pixels: 1 });
  tracker.reset();
});
