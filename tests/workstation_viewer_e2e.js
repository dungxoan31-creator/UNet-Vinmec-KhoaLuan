/* Browser E2E for the modular workstation. Clinical endpoints use synthetic fixtures. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const { spawn } = require("node:child_process");
const { chromium } = require(process.env.PLAYWRIGHT_CORE_PATH || "playwright-core");

const root = path.resolve(__dirname, "..");
const caseId = "synthetic-ui-e2e-study";
const doctorPassword = process.env.APP_DOCTOR_PASSWORD || "doctor-local-test-2026";
const python = process.env.PYTHON || path.join(
  root,
  process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
);
const chromePath = process.env.CHROME_PATH ||
  (process.platform === "win32"
    ? "C:/Program Files/Google/Chrome/Application/chrome.exe"
    : undefined);
let syntheticPng = "";
const calls = { measurements: [], calibrations: [], adnex: [], candidates: [], hitlEvents: [], mockedWrites: [], blockedWrites: [] };
const reviewBatchGate = {
  enabled: false,
  started: null,
  notifyStarted: null,
  response: null,
  release: null,
  payload: null,
};
const errors = [];
const apiTrace = [];
const calibratedImages = new Set();

function rectangleMaskRle(x0 = 224, y0 = 224, x1 = 288, y1 = 288) {
  const mask = new Uint8Array(512 * 512);
  for (let y = y0; y < y1; y++) mask.fill(1, y * 512 + x0, y * 512 + x1);
  const counts = [];
  let value = 0;
  let run = 0;
  for (const pixel of mask) {
    if (pixel === value) run++;
    else {
      counts.push(run);
      value = pixel;
      run = 1;
    }
  }
  counts.push(run);
  return { shape: [512, 512], counts, first_val: 0, encoding: "standard_rle" };
}

function decodeMaskRle(rle) {
  const mask = new Uint8Array(512 * 512);
  let offset = 0;
  let value = rle.first_val;
  for (const count of rle.counts) {
    if (value) mask.fill(1, offset, offset + count);
    offset += count;
    value = 1 - value;
  }
  return mask;
}

function encodeMaskRle(mask) {
  const counts = [];
  let value = mask[0];
  let run = 0;
  for (const pixel of mask) {
    if (pixel === value) run++;
    else {
      counts.push(run);
      value = pixel;
      run = 1;
    }
  }
  counts.push(run);
  return { shape: [512, 512], counts, first_val: mask[0], encoding: "standard_rle" };
}

function candidateMaskRle() {
  const mask = decodeMaskRle(rectangleMaskRle());
  mask[224 * 512 + 224] = 0;
  return encodeMaskRle(mask);
}

function syntheticCase() {
  return {
    study_id: caseId,
    study_code: "E2E-SYNTHETIC-01",
    patient_id: "SYNTHETIC-ONLY",
    study_date: "2026-10-24",
    status: "ANALYZED",
    version: 1,
    review_revision: 0,
    images: ["L", "R"].map((laterality) => ({
      image_id: `synthetic-image-${laterality}`,
      laterality,
      width: 512,
      height: 512,
      prediction: {
        prediction_id: `synthetic-prediction-${laterality}`,
        rle_mask: rectangleMaskRle(),
        measurements: null,
        provenance: { checkpoint_sha256: "synthetic-fixture-only" },
        uncertainty_map_base64: null,
      },
      review: null,
    })),
  };
}

function json(route, data, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  });
}

async function freePort() {
  const listener = net.createServer();
  await new Promise((resolve, reject) => {
    listener.once("error", reject);
    listener.listen(0, "127.0.0.1", resolve);
  });
  const { port } = listener.address();
  await new Promise((resolve, reject) => listener.close((error) => error ? reject(error) : resolve()));
  return port;
}

async function startIsolatedServer() {
  assert.ok(fs.existsSync(python), `Python runner not found: ${python}`);
  const runtime = fs.mkdtempSync(path.join(os.tmpdir(), "clinical-workstation-e2e-"));
  const port = await freePort();
  const child = spawn(python, ["tests/serve_isolated_app.py"], {
    cwd: root,
    env: {
      ...process.env,
      APP_DATA_DIR: runtime,
      APP_DB_PATH: path.join(runtime, "workstation-e2e.sqlite3"),
      APP_JWT_SECRET: "synthetic-ui-e2e-jwt-secret-2026-10-24",
      APP_PATIENT_PID_HMAC_SECRET: "synthetic-ui-e2e-pid-hmac-secret-2026-10-24",
      APP_DOCTOR_PASSWORD: doctorPassword,
      APP_ADMIN_PASSWORD: "synthetic-ui-e2e-admin-password-2026",
      HOST: "127.0.0.1",
      PORT: String(port),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let serverOutput = "";
  child.stdout.on("data", (chunk) => { serverOutput = (serverOutput + chunk).slice(-6000); });
  child.stderr.on("data", (chunk) => { serverOutput = (serverOutput + chunk).slice(-6000); });

  const baseUrl = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null)
      throw new Error(`Isolated app exited before readiness.\n${serverOutput}`);
    try {
      const response = await fetch(`${baseUrl}/api/health/live`);
      if (response.ok) return { child, baseUrl, runtime };
    } catch {
      // Wait for the isolated test server to bind its local port.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  child.kill();
  throw new Error(`Isolated app did not become ready.\n${serverOutput}`);
}

async function waitForPaint(page) {
  await page.evaluate(() => new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve)),
  ));
}

async function test_research_candidate_preview_apply_undo(page, calls, apiTrace) {
  const baseline = await page.evaluate(() => {
    const state = window.__e2eState;
    const image = state.case.images.find((item) => item.laterality === state.side);
    return {
      mask: Array.from(image.mask),
      prediction: JSON.stringify(image.prediction.rle_mask),
      historyLength: image.history.length,
    };
  });
  const writesBefore = calls.mockedWrites.length;
  const requestsBefore = apiTrace.length;

  await page.locator("#researchTab").click();
  const panel = page.locator("#researchCandidatePanel");
  await panel.locator("summary").click();
  const preview = page.locator("#researchCandidatePreview");
  assert.equal(await preview.isDisabled(), true, "all candidate parameters start unanswered");
  await page.locator('[name="min_component_area"]').selectOption("0");
  await page.locator('[name="closing_kernel_size"]').selectOption("0");
  await page.locator('[name="fill_holes"]').selectOption("false");
  await page.locator('[name="smoothing_kernel_size"]').selectOption("none");
  assert.equal(await preview.isEnabled(), true);
  await preview.click();
  await page.locator('#researchCandidateStatus[data-status="PREVIEW"]').waitFor();
  assert.equal(await page.locator("#researchCandidateBaseline").isVisible(), true);
  assert.equal(await page.locator("#researchCandidateCandidate").isVisible(), true);
  assert.equal(await page.locator("#researchCandidateApply").isEnabled(), true);
  const maskPreviewPixels = await page.evaluate(() => {
    const pixel = (selector) => Array.from(document.querySelector(selector)
      .getContext("2d").getImageData(224, 224, 1, 1).data);
    return {
      baseline: pixel("#researchCandidateBaseline"),
      candidate: pixel("#researchCandidateCandidate"),
    };
  });
  assert.notDeepEqual(maskPreviewPixels.baseline, maskPreviewPixels.candidate,
    "mask thumbnails show the candidate difference over the original B-mode image");

  const requested = calls.candidates.at(-1);
  assert.deepEqual(requested, {
    study_id: caseId,
    image_id: "synthetic-image-L",
    prediction_id: "synthetic-prediction-L",
    min_component_area: 0,
    closing_kernel_size: 0,
    fill_holes: false,
    smoothing_kernel_size: null,
  });
  assert.equal("baseline_mask_rle" in requested, false, "client cannot supply its own baseline");
  assert.equal("patient_id" in requested, false, "candidate request contains no patient identifier");

  const previewMask = await page.evaluate(() => {
    const image = window.__e2eState.case.images.find((item) => item.laterality === window.__e2eState.side);
    return Array.from(image.mask);
  });
  assert.deepEqual(previewMask, baseline.mask, "preview does not mutate the editable mask");

  await page.locator("#researchCandidateApply").click();
  const afterApply = await page.evaluate(() => {
    const image = window.__e2eState.case.images.find((item) => item.laterality === window.__e2eState.side);
    return {
      mask: Array.from(image.mask),
      prediction: JSON.stringify(image.prediction.rle_mask),
      historyLength: image.history.length,
    };
  });
  assert.equal(afterApply.mask[224 * 512 + 224], 0, "explicit apply copies the candidate into the editable mask");
  assert.equal(afterApply.historyLength, baseline.historyLength + 1, "candidate apply creates one undo snapshot");
  assert.equal(afterApply.prediction, baseline.prediction, "stored AI prediction remains unchanged");
  const newServerPosts = calls.mockedWrites.slice(writesBefore).filter((entry) => !entry.endsWith("/measurements"));
  assert.deepEqual(newServerPosts, [], "candidate preview/apply issues no clinical persistence request");
  assert.equal(calls.mockedWrites.some((entry) => entry.includes("/reviews/")), false);
  assert.equal(calls.mockedWrites.some((entry) => entry.includes("confirm")), false);

  await page.keyboard.press("Control+z");
  assert.deepEqual(await page.evaluate(() => {
    const image = window.__e2eState.case.images.find((item) => item.laterality === window.__e2eState.side);
    return Array.from(image.mask);
  }), baseline.mask, "undo restores the exact baseline bytes");
  await page.keyboard.press("Control+y");
  assert.deepEqual(await page.evaluate(() => {
    const image = window.__e2eState.case.images.find((item) => item.laterality === window.__e2eState.side);
    return Array.from(image.mask);
  }), afterApply.mask, "redo restores the exact candidate bytes");
  await page.keyboard.press("Control+z");

  reviewBatchGate.enabled = true;
  reviewBatchGate.payload = null;
  reviewBatchGate.started = new Promise((resolve) => { reviewBatchGate.notifyStarted = resolve; });
  reviewBatchGate.response = new Promise((resolve) => { reviewBatchGate.release = resolve; });
  const batchStarted = reviewBatchGate.started;
  await page.locator('[data-action="save-review"]').click();
  await batchStarted;
  await page.waitForFunction(() => window.__e2eState.busy === true);
  const duringSave = await page.evaluate(() => {
    const image = window.__e2eState.case.images.find((item) => item.laterality === window.__e2eState.side);
    return { mask: Array.from(image.mask), historyLength: image.history.length };
  });
  assert.equal(await page.locator("#researchCandidateApply").isDisabled(), true,
    "candidate Apply is visibly locked while the clinical review snapshot is being saved");
  await page.locator("#researchCandidateApply").evaluate((button) =>
    button.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true })),
  );
  assert.deepEqual(await page.evaluate(() => {
    const image = window.__e2eState.case.images.find((item) => item.laterality === window.__e2eState.side);
    return { mask: Array.from(image.mask), historyLength: image.history.length };
  }), duringSave, "even a dispatched click cannot change the mask after the save snapshot");
  assert.deepEqual(reviewBatchGate.payload.reviews[0].verified_mask_rle,
    encodeMaskRle(duringSave.mask), "the delayed save retains the exact snapshotted mask bytes");

  const telemetry = calls.hitlEvents.flat().find((event) =>
    event.event_type === "EDIT_COMMITTED" && event.payload?.tool === "candidate_apply",
  );
  assert.ok(telemetry, "candidate apply is represented in HITL telemetry before review acknowledgement");
  assert.deepEqual({
    algorithm: telemetry.payload.candidate_algorithm,
    version: telemetry.payload.candidate_algorithm_version,
    predictionId: telemetry.payload.candidate_prediction_id,
    modelVersion: telemetry.payload.candidate_model_version,
    minComponentArea: telemetry.payload.candidate_min_component_area,
    closingKernelSize: telemetry.payload.candidate_closing_kernel_size,
    fillHoles: telemetry.payload.candidate_fill_holes,
    smoothingKernelSize: telemetry.payload.candidate_smoothing_kernel_size,
  }, {
    algorithm: "explicit_morphology_candidate",
    version: "1.0.0",
    predictionId: "synthetic-prediction-L",
    modelVersion: "synthetic-e2e-v1",
    minComponentArea: 0,
    closingKernelSize: 0,
    fillHoles: false,
    smoothingKernelSize: null,
  }, "saved HITL provenance identifies the transform and source prediction");
  const candidateWatermark = reviewBatchGate.payload.telemetry_tasks.find((item) =>
    item.task_id === telemetry.task_id,
  );
  assert.ok(candidateWatermark && candidateWatermark.last_seq >= telemetry.seq,
    "review save watermark includes the candidate, undo and redo audit sequence");

  reviewBatchGate.release({ status: 200, body: { status: "SUCCESS", reviews: [] } });
  await page.waitForFunction(() => window.__e2eState.busy === false);
  reviewBatchGate.enabled = false;

  const candidateTrace = apiTrace.slice(requestsBefore).filter((entry) => entry.includes("/api/v1/segment/candidate"));
  assert.deepEqual(candidateTrace, ["POST /api/v1/segment/candidate"]);
  console.log("PASS: RUO candidate preview stays read-only; explicit apply is undoable and does not persist the AI prediction");
}

async function test_orads_quick_pick_is_empty_by_default_and_updates_existing_draft(page, calls) {
  await page.locator("#oradsQuickPickMenu > summary").click();
  const quickPicks = page.locator('[data-action="orads-quick-pick"]');
  assert.deepEqual(
    await quickPicks.evaluateAll((buttons) => buttons.map((button) => button.dataset.value)),
    ["O-RADS 0", "O-RADS 1", "O-RADS 2", "O-RADS 3", "O-RADS 4", "O-RADS 5"],
    "quick-pick buttons mirror the existing select options",
  );
  assert.equal(await page.locator("#oradsScore").inputValue(), "", "no category is preselected");
  assert.deepEqual(
    await quickPicks.evaluateAll((buttons) => buttons.map((button) => button.getAttribute("aria-pressed"))),
    ["false", "false", "false", "false", "false", "false"],
  );

  const localDraftBefore = await page.evaluate(() => {
    const state = window.__e2eState;
    return localStorage.getItem(`ova.draft.live.${state.user?.id}.${state.case.study_id}`);
  });
  const writesBefore = calls.mockedWrites.length;
  const requestsBefore = apiTrace.length;
  await page.locator('[data-action="orads-quick-pick"][data-value="O-RADS 3"]').click();
  assert.equal(await page.locator("#oradsScore").inputValue(), "O-RADS 3");
  assert.deepEqual(await page.evaluate(() => {
    const state = window.__e2eState;
    const image = state.case.images.find((item) => item.laterality === state.side);
    return { value: image.orads, dirty: state.dirty };
  }), { value: "O-RADS 3", dirty: true }, "selection reuses the clinician draft change path");
  assert.equal(await page.locator('[data-action="orads-quick-pick"][data-value="O-RADS 3"]').getAttribute("aria-pressed"), "true");
  await page.waitForTimeout(250);
  assert.equal(await page.evaluate(() => {
    const state = window.__e2eState;
    return localStorage.getItem(`ova.draft.live.${state.user?.id}.${state.case.study_id}`);
  }), localDraftBefore, "quick-pick updates the in-memory draft without auto-saving it");
  assert.equal(calls.mockedWrites.length, writesBefore, "draft selection does not persist before review save");
  assert.deepEqual(apiTrace.slice(requestsBefore), [], "draft selection starts no API request");
}

async function test_orads_quick_pick_respects_readonly_and_does_not_write(page, calls) {
  const selected = await page.locator("#oradsScore").inputValue();
  const writesBefore = calls.mockedWrites.length;
  await page.evaluate(() => window.dispatchEvent(new CustomEvent("ova:lease-lost")));
  await page.waitForFunction(() => {
    const select = document.querySelector("#oradsScore");
    const buttons = [...document.querySelectorAll('[data-action="orads-quick-pick"]')];
    return select?.disabled && buttons.length === 6 && buttons.every((button) => button.disabled);
  });
  assert.equal(await page.locator("#oradsScore").inputValue(), selected, "lease loss preserves the existing clinician choice");
  assert.equal(calls.mockedWrites.length, writesBefore, "readonly transition issues no clinical write");
}

async function test_neutral_note_phrases_are_local_and_restore_caret(page, calls) {
  await page.waitForTimeout(250);
  const notes = page.locator("#notes");
  const requestsBefore = apiTrace.length;
  const writesBefore = calls.mockedWrites.length;
  await notes.fill(".obs");
  assert.equal(await notes.inputValue(), ".obs", "typing a token alone does not expand a longer word prefix");
  await notes.press("Space");
  assert.equal(await notes.inputValue(), "Mô tả:  ", "a neutral token expands when followed by a boundary");
  assert.equal(
    await notes.evaluate((element) => element.selectionStart),
    "Mô tả:  ".length,
    "the caret remains after the inserted phrase and original delimiter",
  );
  assert.deepEqual(await page.evaluate(() => {
    const state = window.__e2eState;
    const image = state.case.images.find((item) => item.laterality === state.side);
    return { note: image.notes, dirty: state.dirty };
  }), { note: "Mô tả:  ", dirty: true }, "the expanded text follows the existing doctor draft path");
  await page.waitForTimeout(250);
  assert.deepEqual(apiTrace.slice(requestsBefore), [], "note typing and expansion do not call clinical APIs");
  assert.equal(calls.mockedWrites.length, writesBefore, "phrase expansion causes no API write");
  await notes.fill("");
}

async function test_overlay_visibility_button_and_o_shortcut_preserve_mask_and_dirty_state(page, calls) {
  const toggle = page.locator('[data-action="overlay-visibility"]');
  assert.equal(await toggle.count(), 1, "the accessible overlay control is present");
  assert.equal(await toggle.getAttribute("aria-label"), "Hiện/ẩn lớp phủ AI");

  const waitForOverlay = async (visible) => {
    await page.waitForFunction(
      (expected) => document.querySelector('[data-action="overlay-visibility"]')?.getAttribute("aria-pressed") === String(expected),
      visible,
    );
    await waitForPaint(page);
  };
  const centerPixel = () => page.evaluate(() => {
    const canvas = document.querySelector("#viewport");
    return Array.from(canvas.getContext("2d").getImageData(Math.floor(canvas.width / 2), Math.floor(canvas.height / 2), 1, 1).data);
  });
  const activeMask = () => page.evaluate(() => {
    const state = window.__e2eState;
    const image = state.case.images.find((item) => item.laterality === state.side);
    return { mask: Array.from(image.mask), dirty: state.dirty };
  });

  await page.locator("#viewport").focus();
  await page.keyboard.press("k");
  await page.locator('[data-action="layer-0"]').click();
  await waitForOverlay(false);
  const baseline = await activeMask();
  const writesBefore = calls.mockedWrites.length;
  const rawPixel = await centerPixel();
  await toggle.click();
  await waitForOverlay(true);
  const overlayPixel = await centerPixel();
  assert.notDeepEqual(overlayPixel.slice(0, 3), rawPixel.slice(0, 3), "toggle displays the overlay pixels");
  assert.deepEqual(await activeMask(), baseline, "view-only toggle preserves mask bytes and dirty state");
  await toggle.click();
  await waitForOverlay(false);
  assert.deepEqual(await centerPixel(), rawPixel, "second toggle restores the prior raw layer");
  assert.deepEqual(await activeMask(), baseline);

  await page.locator("#viewport").evaluate((element) => {
    element.focus();
    element.dispatchEvent(new KeyboardEvent("keydown", { key: "o", bubbles: true }));
  });
  await waitForOverlay(true);
  assert.equal(await page.locator("#viewport").evaluate((element) => document.activeElement === element), true,
    "O changes the view without moving keyboard focus");
  await page.locator("#notes").evaluate((element) => {
    element.focus();
    element.dispatchEvent(new KeyboardEvent("keydown", { key: "o", bubbles: true }));
  });
  assert.equal(await toggle.getAttribute("aria-pressed"), "true", "O does not hijack note editing");
  await page.locator("#oradsScore").evaluate((element) => {
    element.focus();
    element.dispatchEvent(new KeyboardEvent("keydown", { key: "o", bubbles: true }));
  });
  assert.equal(await toggle.getAttribute("aria-pressed"), "true", "O does not hijack select controls");

  await page.evaluate(() => document.querySelector("#modal").showModal());
  await page.locator("#modal").evaluate((element) =>
    element.dispatchEvent(new KeyboardEvent("keydown", { key: "o", bubbles: true })),
  );
  assert.equal(await toggle.getAttribute("aria-pressed"), "true", "O is ignored while a dialog is open");
  await page.evaluate(() => document.querySelector("#modal").close());
  await page.locator("#viewport").evaluate((element) => {
    const event = new KeyboardEvent("keydown", { key: "o", bubbles: true });
    Object.defineProperty(event, "isComposing", { value: true });
    element.dispatchEvent(event);
  });
  assert.equal(await toggle.getAttribute("aria-pressed"), "true", "O is ignored during IME composition");
  assert.equal(calls.mockedWrites.length, writesBefore, "overlay controls issue no API writes");

  await page.locator('[data-action="layer-1"]').click();
  await waitForOverlay(false);
  await page.keyboard.down("Space");
  await page.keyboard.press("o");
  await waitForPaint(page);
  assert.deepEqual(await centerPixel(), rawPixel, "Space still peeks the unmodified source while O changes the underlying view");
  await page.keyboard.up("Space");
  await waitForOverlay(true);
  await toggle.focus();
  await page.keyboard.press("Tab");
  assert.notEqual(await page.evaluate(() => document.activeElement?.dataset?.action), "overlay-visibility",
    "Tab retains native focus navigation");
  const beforeSideChange = await activeMask();
  const startingSide = await page.evaluate(() => window.__e2eState.side);
  const otherSide = startingSide === "L" ? "R" : "L";
  const rightMeasurement = page.waitForResponse((response) =>
    new URL(response.url()).pathname === `/api/images/synthetic-image-${otherSide}/measurements` &&
    response.request().method() === "POST",
  );
  await page.locator(`[data-action="side-${otherSide}"]`).click();
  await page.waitForFunction((side) => window.__e2eState.side === side, otherSide);
  await rightMeasurement;
  const alternateBaseline = await activeMask();
  const alternateWritesBefore = calls.mockedWrites.length;
  await toggle.click();
  await waitForOverlay(false);
  assert.deepEqual(await activeMask(), alternateBaseline, "side change cannot apply a stale or mutate a current mask");
  assert.equal(calls.mockedWrites.length, alternateWritesBefore,
    `side-specific overlay toggle issues no API writes: ${calls.mockedWrites.slice(alternateWritesBefore).join(", ")}`);
  await page.locator(`[data-action="side-${startingSide}"]`).click();
  await page.waitForFunction((side) => window.__e2eState.side === side, startingSide);
  assert.deepEqual(await activeMask(), beforeSideChange, "returning to the prior side restores its unchanged mask");
  await page.keyboard.press("k");
}

async function main() {
  const server = await startIsolatedServer();
  let browser;
  try {
    browser = await chromium.launch({ headless: true, ...(chromePath ? { executablePath: chromePath } : {}) });
    const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
    syntheticPng = await page.evaluate(() => {
      const source = document.createElement("canvas");
      source.width = source.height = 512;
      const context = source.getContext("2d");
      const gradient = context.createLinearGradient(0, 0, 512, 512);
      gradient.addColorStop(0, "#1c2c37");
      gradient.addColorStop(1, "#b8c4c8");
      context.fillStyle = gradient;
      context.fillRect(0, 0, 512, 512);
      context.beginPath();
      context.arc(256, 256, 92, 0, Math.PI * 2);
      context.fillStyle = "#24313a";
      context.fill();
      context.strokeStyle = "#dce8ea";
      context.lineWidth = 8;
      context.stroke();
      return source.toDataURL("image/png");
    });
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });

    await page.route("**/api/**", async (route) => {
      const request = route.request();
      const method = request.method();
      const url = new URL(request.url());
      const pathName = url.pathname;
      apiTrace.push(`${method} ${pathName}`);
      const imageId = pathName.match(/^\/api\/images\/(synthetic-image-[LR])\/(.+)$/);

      if (pathName === `/api/cases/${caseId}` && method === "GET")
        return json(route, syntheticCase());
      if (pathName === `/api/workspace/cases/${caseId}/lease` && method === "POST") {
        calls.mockedWrites.push(`${method} ${pathName}`);
        return json(route, { granted: true, lease_token: "synthetic-lease-token", expires_at: "2099-01-01T00:00:00Z" });
      }
      if (pathName === `/api/workspace/cases/${caseId}/lease` && method === "DELETE") {
        calls.mockedWrites.push(`${method} ${pathName}`);
        return route.fulfill({ status: 204, body: "" });
      }
      if (pathName === "/api/hitl/sessions" && method === "POST") {
        calls.mockedWrites.push(`${method} ${pathName}`);
        return json(route, { id: "synthetic-hitl-session" });
      }
      if (pathName === "/api/hitl/events" && method === "POST") {
        calls.hitlEvents.push(request.postDataJSON()?.events || []);
        return json(route, { success: true, count: 1 });
      }
      if (pathName === "/api/hitl/sessions/synthetic-hitl-session/events" && method === "POST") {
        calls.hitlEvents.push(request.postDataJSON()?.events || []);
        calls.mockedWrites.push(`${method} ${pathName}`);
        return json(route, { accepted: true, count: 1 });
      }
      if (pathName === "/api/reviews/batch" && method === "POST" && reviewBatchGate.enabled) {
        reviewBatchGate.payload = request.postDataJSON();
        reviewBatchGate.notifyStarted?.();
        const response = await reviewBatchGate.response;
        return json(route, response.body, response.status);
      }
      if (imageId?.[2] === "viewer-source" && method === "GET")
        return json(route, { image_id: imageId[1], original_image_base64: syntheticPng });
      if (imageId?.[2] === "source.png" && method === "GET")
        return route.fulfill({ contentType: "image/png", body: Buffer.from(syntheticPng.split(",")[1], "base64") });
      if (imageId?.[2] === "measurements" && method === "POST") {
        const payload = request.postDataJSON();
        calls.measurements.push({ imageId: imageId[1], hasMask: Array.isArray(payload.rle_mask?.counts) });
        calls.mockedWrites.push(`${method} ${pathName}`);
        return json(route, {
          max_diameter_px: 64,
          ortho_diameter_px: 64,
          total_area_px: 4096,
          max_diameter_mm: calibratedImages.has(imageId[1]) ? 32 : null,
          ortho_diameter_mm: calibratedImages.has(imageId[1]) ? 32 : null,
          total_area_cm2: calibratedImages.has(imageId[1]) ? 10.24 : null,
          pixel_spacing_mm: calibratedImages.has(imageId[1]) ? 0.5 : null,
          calibration_source: calibratedImages.has(imageId[1]) ? "MANUAL" : null,
          calibrated: calibratedImages.has(imageId[1]),
          coordinate_space: "decoded-source-image",
          lesions: [],
        });
      }
      if (imageId?.[2] === "calibrate" && method === "POST") {
        calibratedImages.add(imageId[1]);
        calls.calibrations.push(Number(url.searchParams.get("pixel_spacing_mm")));
        calls.mockedWrites.push(`${method} ${pathName}`);
        return json(route, { status: "CALIBRATED", pixel_spacing_mm: Number(url.searchParams.get("pixel_spacing_mm")) });
      }
      if (pathName === "/api/v1/cdss/evaluate" && method === "POST") {
        calls.adnex.push(request.postDataJSON());
        calls.mockedWrites.push(`${method} ${pathName}`);
        return json(route, {
          adnex_evaluation: {
            status: "EVALUATED_RUO",
            model_variant: "WITHOUT_CA125",
            probabilities: {
              benign: 0.8,
              borderline: 0.1,
              stage_i_primary_malignancy: 0.05,
              stage_ii_iv_primary_malignancy: 0.03,
              secondary_metastatic: 0.02,
            },
            total_malignancy_probability: 0.1,
          },
        });
      }
      if (pathName === "/api/v1/segment/candidate" && method === "POST") {
        const payload = request.postDataJSON();
        calls.candidates.push(payload);
        return json(route, {
          success: true,
          baseline_mask_rle: rectangleMaskRle(),
          candidate_mask_rle: candidateMaskRle(),
          candidate_parameters: {
            min_component_area: payload.min_component_area,
            closing_kernel_size: payload.closing_kernel_size,
            fill_holes: payload.fill_holes,
            smoothing_kernel_size: payload.smoothing_kernel_size,
          },
          provenance: {
            prediction_id: payload.prediction_id,
            model_version: "synthetic-e2e-v1",
            checkpoint_sha256: null,
            algorithm: "explicit_morphology_candidate",
            algorithm_version: "1.0.0",
          },
        });
      }

      const allowedServerRequests = new Set([
        "POST /api/auth/login",
        "POST /api/auth/logout",
        "POST /api/cases/search", // Read-only paginated case search.
      ]);
      if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && !allowedServerRequests.has(`${method} ${pathName}`)) {
        calls.blockedWrites.push(`${method} ${pathName}`);
        return route.abort("blockedbyclient");
      }
      return route.continue();
    });

    await page.goto(`${server.baseUrl}/#login`, { waitUntil: "networkidle" });
    await page.locator("#authForm [name=username]").fill("doctor");
    await page.locator("#authForm [name=password]").fill(doctorPassword);
    await page.locator("#authForm button[type=submit]").click();
    await page.waitForFunction(() => location.hash === "#dashboard");
    await page.evaluate((id) => { window.__e2eStudyId = id; }, caseId);
    await page.evaluate(async () => {
      window.__e2eState = (await import("/static/app/state.js")).state;
    });
    await page.evaluate((id) => { location.hash = `#viewer/${id}`; }, caseId);
    const canvas = page.locator("#viewport");
    try {
      await canvas.waitFor({ state: "visible", timeout: 10000 });
    } catch (error) {
      console.error(JSON.stringify({
        location: await page.evaluate(() => location.href),
        pageText: (await page.locator("#page").innerText()).slice(0, 1800),
        apiTrace,
        errors,
      }, null, 2));
      throw error;
    }
    await page.waitForFunction(() =>
      window.__e2eState?.case?.study_id === window.__e2eStudyId &&
      window.__e2eState.case.images.find((image) => image.laterality === "L")?.seen === true,
    );
    assert.equal(await page.locator("#calibrationBadge").textContent(), "");
    const initialReviewState = await page.evaluate(() => {
      const { state } = { state: window.__e2eState };
      return {
        sides: state.case.images.map((image) => ({ laterality: image.laterality, seen: image.seen ?? null })),
        saveDisabled: document.querySelector('[data-action="save-review"]').disabled,
        signDisabled: document.querySelector('[data-action="sign"]').disabled,
      };
    });
    assert.equal(await page.locator('[data-action="save-review"]').isDisabled(), true,
      "Review remains disabled until both sides are visibly reviewed");
    assert.equal(await page.locator('[data-action="sign"]').isDisabled(), true,
      "Sign-off remains disabled until both sides are visibly reviewed");

    const rightSideMeasurement = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/images/synthetic-image-R/measurements" &&
      response.request().method() === "POST",
    );
    await page.locator('[data-action="side-R"]').click();
    await page.waitForFunction(() =>
      window.__e2eState?.side === "R" && window.__e2eState.case.images.every((image) => image.seen === true),
    );
    await rightSideMeasurement;
    assert.equal(await page.locator('[data-action="save-review"]').isEnabled(), true);
    assert.equal(await page.locator('[data-action="sign"]').isDisabled(), true,
      "Preliminary sign-off stays disabled while the server capability is unavailable");
    assert.match(await page.locator('[data-action="sign"]').textContent(), /chưa khả dụng/);
    assert.equal(calls.mockedWrites.some((entry) => entry.includes("sign-preliminary")), false,
      "RUO mode must not submit a preliminary sign-off");
    await test_orads_quick_pick_is_empty_by_default_and_updates_existing_draft(page, calls);
    await test_overlay_visibility_button_and_o_shortcut_preserve_mask_and_dirty_state(page, calls);
    await test_neutral_note_phrases_are_local_and_restore_caret(page, calls);
    console.log("PASS: bilateral review gate and fail-closed sign-off");

    await page.locator('[data-action="side-L"]').click();
    await page.locator("#researchTab").click();
    await test_research_candidate_preview_apply_undo(page, calls, apiTrace);
    await page.locator("#adnexPanel > summary").click();
    await page.locator("#adnexVariant").selectOption("WITHOUT_CA125");
    await page.locator("#adnexAge").fill("45");
    await page.locator("#adnexOncology").selectOption("false");
    await page.locator("#adnexPersistent").selectOption("true");
    await page.locator("#adnexSurgery").selectOption("false");
    await page.locator("#adnexComplete").selectOption("true");
    await page.locator("#adnexPhysiologic").selectOption("false");
    await page.locator("#adnexDiameter").fill("40");
    await page.locator("#adnexSolidDiameter").fill("0");
    await page.locator("#adnexLocules").fill("1");
    await page.locator("#adnexPapillary").fill("0");
    await page.locator("#adnexShadow").selectOption("true");
    await page.locator("#adnexAscites").selectOption("false");
    await page.locator("#adnexEvaluate").click();
    await page.locator('#adnexResult[data-status="EVALUATED_RUO"]').waitFor();
    assert.equal(calls.adnex.length, 1);
    assert.deepEqual(calls.adnex[0].adnex_inputs, {
      model_variant: "WITHOUT_CA125",
      age_years: 45,
      is_oncology_center: false,
      is_persistent_adnexal_mass: true,
      surgery_indicated: false,
      assessment_source: "clinician",
      modality: "ultrasound_2d",
      ultrasound_exam_complete: true,
      max_lesion_diameter_mm: 40,
      largest_solid_component_mm: 0,
      cyst_locules_count: 1,
      papillary_projections_count: 0,
      acoustic_shadowing: true,
      has_ascites: false,
      physiologic_follicle_confirmed: false,
    });
    assert.equal(await page.locator("#adnexTotalMalignancyProbability").isVisible(), true);
    await page.locator("#adnexVariant").selectOption("WITH_CA125");
    await page.locator("#adnexEvaluate").click();
    assert.equal(calls.adnex.length, 1, "CA-125 is required for the selected variant");
    await page.locator("#adnexCa125").fill("25");
    await page.locator("#adnexEvaluate").click();
    await page.waitForFunction(() => document.querySelectorAll('#adnexResult[data-status="EVALUATED_RUO"]').length === 1);
    assert.equal(calls.adnex.length, 2);
    assert.equal(calls.adnex[1].adnex_inputs.ca125_u_ml, 25);
    console.log("PASS: ADNEX inputs, CA-125 validation and research-only result rendering");

    await page.locator("#clinicalTab").click();
    assert.equal(await page.locator("#clinicalPanel").isVisible(), true);
    assert.equal(await page.locator(".viewer-more-actions").evaluate((element) => element.open), false,
      "Outside interaction dismisses the open action menu");
    await page.locator("#notes").fill("Synthetic E2E note only");
    await page.locator("#iotaMorphology").selectOption("Nang nhiều thùy");
    await page.locator("#oradsScore").selectOption("O-RADS 3");
    await page.locator("#morphology").fill("Synthetic morphology");
    await page.locator('[data-chip="Bóng cản âm"]').click();
    assert.equal(await page.locator("#notes").inputValue(), "Synthetic E2E note only");
    assert.equal(await page.locator("#oradsScore").inputValue(), "O-RADS 3");
    await page.locator('[data-action="side-R"]').click();
    await page.waitForFunction(() => window.__e2eState.side === "R");
    assert.equal(await page.locator("#notes").inputValue(), "", "Clinical text must not copy to the other side");
    await page.locator('[data-action="side-L"]').click();
    await page.waitForFunction(() => window.__e2eState.side === "L");
    assert.equal(await page.locator("#notes").inputValue(), "Synthetic E2E note only");
    console.log("PASS: clinician-entered descriptors and side-specific notes");

    await page.locator(".view-more summary").click();
    await page.locator('[data-action="contour"]').click();
    await page.locator('[data-action="layer-1"]').click();
    await waitForPaint(page);
    const centerPixel = () => page.evaluate(() => {
      const element = document.querySelector("#viewport");
      const context = element.getContext("2d");
      return Array.from(context.getImageData(Math.floor(element.width / 2), Math.floor(element.height / 2), 1, 1).data);
    });
    const maskPixel = await centerPixel();
    assert.ok(maskPixel[1] > 100 && maskPixel[2] > 100,
      "Mask layer displays the synthetic lesion overlay at the active opacity");
    await page.keyboard.down("Space");
    await waitForPaint(page);
    const rawPixel = await centerPixel();
    await page.keyboard.up("Space");
    assert.notDeepEqual(rawPixel.slice(0, 3), maskPixel.slice(0, 3), "Space is a momentary raw-image peek, not approval");
    assert.equal(calls.mockedWrites.some((entry) => entry.includes("/reviews/")), false);
    assert.equal(calls.mockedWrites.some((entry) => entry.includes("sign-preliminary")), false);
    await page.locator('[data-action="layer-2"]').click();
    await waitForPaint(page);
    await page.evaluate(() => {
      const slider = document.querySelector("#opacity");
      slider.value = "0";
      slider.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await waitForPaint(page);
    const noOverlayPixel = await centerPixel();
    await page.evaluate(() => {
      const slider = document.querySelector("#opacity");
      slider.value = "50";
      slider.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await waitForPaint(page);
    const overlayPixel = await centerPixel();
    assert.notDeepEqual(overlayPixel.slice(0, 3), noOverlayPixel.slice(0, 3));
    assert.equal(await page.locator("#uncertaintyToggle").isDisabled(), true,
      "Uncertainty display stays unavailable when the case has no map");
    console.log("PASS: raw/mask/overlay layers, Space peek, opacity and fail-closed uncertainty map");

    const rangeValue = (selector) => page.locator(selector).evaluate((element) => element.value);
    await page.locator("#viewport").focus();
    await page.keyboard.press("b");
    assert.equal(await page.locator('[data-tool="brush"]').getAttribute("aria-pressed"), "true");
    await page.keyboard.press("]");
    assert.equal(await rangeValue("#brushSize"), "18");
    await page.keyboard.press("[");
    assert.equal(await rangeValue("#brushSize"), "16");
    await page.keyboard.press("e");
    assert.equal(await page.locator('[data-tool="erase"]').getAttribute("aria-pressed"), "true");

    const maskCount = () => page.evaluate(async () => {
      const { state } = await import("/static/app/state.js");
      return state.case.images.find((image) => image.laterality === state.side).mask.reduce((sum, value) => sum + value, 0);
    });
    const setMaskFixture = (pattern) => page.evaluate((name) => {
      const image = window.__e2eState.case.images.find((item) => item.laterality === window.__e2eState.side);
      image.mask.fill(0);
      if (name === "single") image.mask[200 * 512 + 200] = 1;
      if (name === "ring") {
        for (let y = 100; y < 112; y++)
          for (let x = 100; x < 112; x++)
            if (x < 103 || x >= 109 || y < 103 || y >= 109) image.mask[y * 512 + x] = 1;
      }
    }, pattern);
    const initialMaskCount = await maskCount();
    const box = await page.locator("#viewport").boundingBox();
    const point = { x: box.x + box.width * 0.72, y: box.y + box.height * 0.72 };
    await page.locator('[data-tool="brush"]').click();
    await page.mouse.click(point.x, point.y);
    const paintedMaskCount = await maskCount();
    assert.ok(paintedMaskCount > initialMaskCount, "Brush changes the active side mask");
    await page.keyboard.press("Control+z");
    assert.equal(await maskCount(), initialMaskCount, "Undo restores the prior mask");
    await page.keyboard.press("Control+Shift+z");
    assert.equal(await maskCount(), paintedMaskCount, "Redo restores the edited mask");
    await page.locator('[data-tool="erase"]').click();
    await page.mouse.click(point.x, point.y);
    assert.ok(await maskCount() < paintedMaskCount, "Eraser removes mask pixels");
    await page.locator('[data-tool="pan"]').click();
    assert.equal(await page.locator("#viewport").evaluate((element) => getComputedStyle(element).cursor), "grab");
    await page.locator('[data-tool="fit"]').click();

    await page.locator(".tool-more > summary").click();
    await setMaskFixture("single");
    await page.locator('[data-tool="small"]').click();
    assert.equal(await maskCount(), 0, "Small-component cleanup removes an isolated pixel");
    await page.locator(".tool-more > summary").click();
    await setMaskFixture("ring");
    await page.locator('[data-tool="fill"]').click();
    assert.equal(await page.evaluate(() => window.__e2eState.case.images.find((image) => image.laterality === "L").mask[105 * 512 + 105]), 1,
      "Fill closes an enclosed hole without changing the source image");
    await setMaskFixture("single");
    await page.locator(".tool-more > summary").click();
    await page.locator('[data-tool="smooth"]').click();
    assert.equal(await maskCount(), 0, "Smoothing removes an isolated one-pixel spike");

    await setMaskFixture("empty");
    await page.locator(".tool-more > summary").click();
    await page.locator('[data-tool="polygon"]').click();
    const polygonBox = await page.locator("#viewport").boundingBox();
    const polygonPoint = (x, y) => ({ x: polygonBox.x + polygonBox.width * x, y: polygonBox.y + polygonBox.height * y });
    for (const [x, y] of [[0.34, 0.38], [0.48, 0.38], [0.48, 0.54]]) {
      const p = polygonPoint(x, y);
      await page.mouse.click(p.x, p.y);
    }
    await page.keyboard.press("g");
    const polygonMaskCount = await maskCount();
    assert.ok(polygonMaskCount > 0, "G completes and fills the clinician-drawn polygon");
    await page.keyboard.press("Control+z");
    assert.equal(await maskCount(), 0, "Undo restores the mask before polygon fill");
    await page.keyboard.press("Control+y");
    assert.equal(await maskCount(), polygonMaskCount, "Redo restores the clinician-drawn polygon fill");
    await page.keyboard.press("Control+z");
    for (const [x, y] of [[0.34, 0.38], [0.48, 0.38], [0.48, 0.54]]) {
      const p = polygonPoint(x, y);
      await page.mouse.click(p.x, p.y);
    }
    const closePoint = polygonPoint(0.34, 0.38);
    await page.mouse.dblclick(closePoint.x, closePoint.y);
    assert.ok(await maskCount() > 0, "Double-click polygon completion remains available");
    await page.locator(".tool-more > summary").click();
    await page.locator('[data-tool="clear"]').click();
    await page.locator('#modal button[value="confirm"]').click();
    assert.equal(await maskCount(), 0, "Clear requires explicit confirmation");
    await page.locator(".tool-more > summary").click();
    await page.locator('[data-tool="reset"]').click();
    await page.locator('#modal button[value="confirm"]').click();
    assert.equal(await maskCount(), 4096, "Reset restores the original AI mask");
    await page.locator('[data-action="no-lesion"]').click();
    await page.locator('#modal button[value="confirm"]').click();
    assert.equal(await maskCount(), 0, "No-lesion action only clears the current mask");
    await page.locator('[data-action="manual"]').click();
    await page.locator('#modal button.btn[value="cancel"]').click();
    console.log("PASS: Brush/Eraser, polygon, fill, small, smooth, clear/reset, B/E/[ / ], Undo/Redo, Pan/Fit");

    await page.locator(".tool-more > summary").click();
    await page.locator('[data-tool="fullscreen"]').click();
    await page.waitForFunction(() => document.fullscreenElement !== null);
    await page.locator(".tool-more > summary").click();
    await page.locator('[data-tool="fullscreen"]').click();
    await page.waitForFunction(() => document.fullscreenElement === null);

    await page.locator("#viewerAdjustments > summary").click();
    await page.evaluate(() => {
      const slider = document.querySelector("#displayPreset");
      slider.value = "contrast";
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    });
    assert.equal(await rangeValue("#brightness"), "100");
    assert.equal(await rangeValue("#contrast"), "140");
    await page.locator('[data-action="image-reset"]').click();
    assert.equal(await rangeValue("#contrast"), "100");
    await page.locator('[data-action="calibrate"]').click();
    await page.locator('#modal input[name="pixels"]').fill("20");
    await page.locator('#modal input[name="mm"]').fill("10");
    await page.locator('#modal button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector("#calibrationBadge")?.textContent === "Nhập tay");
    assert.deepEqual(calls.calibrations, [0.5], "Manual calibration is sent only from an explicit physician input");
    console.log("PASS: image adjustments, reset and explicit manual calibration");

    await page.locator("#viewerAdjustments > summary").click();
    await page.locator(".view-more summary").click();
    await page.locator('[data-action="bilateral"]').click();
    await page.locator("#secondPane").waitFor({ state: "visible" });
    assert.equal(await page.locator("#secondPane .canvas-label").textContent(), "Bên còn lại · chỉ xem");
    await page.locator(".view-more summary").click();
    await page.locator('[data-action="compare"]').click();
    assert.equal(await page.locator("#secondPane .canvas-label").textContent(), "Ảnh gốc");
    await page.locator(".view-more summary").click();
    await page.locator('[data-action="compare"]').click();
    await page.waitForFunction(() => document.querySelector("#secondPane").hidden);
    await page.locator("#researchTab").click();
    await page.locator("#clinicalTab").focus();
    await page.keyboard.press("ArrowRight");
    assert.equal(await page.locator("#researchTab").getAttribute("aria-selected"), "true");
    console.log("PASS: same-screen bilateral reference and accessible panel tabs");

    for (const width of [1440, 1024, 768, 390]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true,
        `No horizontal overflow at ${width}px`);
      assert.equal(await page.locator("#viewport").isVisible(), true);
    }
    await page.setViewportSize({ width: 1440, height: 960 });
    await test_orads_quick_pick_respects_readonly_and_does_not_write(page, calls);
    await page.locator("#viewport").focus();
    await page.keyboard.press("Control+p");
    await page.waitForFunction(() => location.hash.startsWith(`#report/${window.__e2eStudyId}`));
    await page.locator("#reportData .report").waitFor();
    assert.deepEqual(errors, [], errors.join("\n"));
    assert.deepEqual(calls.blockedWrites, [], calls.blockedWrites.join("\n"));
    assert.equal(calls.measurements.length > 0, true, "Viewer measurement calls were exercised");
    console.log("PASS: responsive viewports, report shortcut and no browser/runtime errors");

    await page.locator("#accountMenu").click();
    await page.locator('[data-action="logout"]').click();
    await page.locator("#authForm").waitFor();
    assert.deepEqual(errors, [], errors.join("\n"));
    console.log(JSON.stringify({
      status: "PASS",
      flow: "synthetic-only modular workstation viewer E2E",
      checkedViewports: [1440, 1024, 768, 390],
      mockedClinicalWrites: calls.mockedWrites.length,
      blockedUnexpectedWrites: calls.blockedWrites.length,
      measurementCalls: calls.measurements.length,
      adnexEvaluations: calls.adnex.length,
      calibrationCalls: calls.calibrations.length,
      pageErrors: errors.length,
      runtime: server.runtime,
    }));
  } finally {
    await browser?.close();
    server.child.kill();
  }
}

main().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
