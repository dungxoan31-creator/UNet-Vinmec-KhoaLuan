import test, { beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { maskDraftKey, state } from '../frontend/app/state.js';
import { tracker } from '../frontend/app/hitl-tracker.js';
import { saveResearchReview } from '../frontend/app/review.js';

Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { onLine: true } });
const busyTransitions = [];
const toasts = [];
globalThis.window = {
  dispatchEvent(event) {
    if (event.type === 'ova:busy-changed') busyTransitions.push(state.busy);
  },
};
globalThis.document = { createElement: () => ({ remove() {} }), querySelector: () => ({ append(node) { toasts.push(node.textContent); } }) };
const realTimeout = globalThis.setTimeout;
globalThis.setTimeout = (...args) => { const timer = realTimeout(...args); timer.unref?.(); return timer; };
let removals;
let removedKeys;
beforeEach(() => {
  removals = 0;
  removedKeys = [];
  busyTransitions.length = 0;
  toasts.length = 0;
  globalThis.navigator.onLine = true;
  globalThis.localStorage = { removeItem(key) { removals++; removedKeys.push(key); } };
  Object.assign(state, {
    user: { id: 'user', username: 'doctor', role: 'DOCTOR' }, token: 'token',
    busy: false, dirty: true, capabilities: { manual_review: false },
    editing: { caseId: 'study', allowed: true, leaseToken: 'lease', pageInstanceId: 'page' },
    case: { study_id: 'study', status: 'ANALYZED', review_revision: 0,
      images: ['L', 'R'].map(side => ({ image_id: side, laterality: side, seen: true,
        prediction: { prediction_id: 'p-' + side }, mask: new Uint8Array(512 * 512),
        aiMask: new Uint8Array(512 * 512), notes: '', morphology: '', morphologyDesc: '', orads: '' })) },
    pendingReviewTelemetryAck: null, pendingReview: null, currentReviewRequestId: null,
    lastClinicalSnapshot: null, lastReviewTimeSpent: null, routeController: null,
  });
  Object.assign(tracker, { getTaskMetrics: () => null, getStudyId: () => null, getSessionId: () => null,
    getWatermarks: () => [], track() {}, confirmAck() {}, recordSaveFailure() {}, flush: async () => {} });
});

test('one-sided save confirmation names only the side and images actually saved', async () => {
  state.case.images = [state.case.images[0]];
  globalThis.fetch = async (_url, options) => response(ack(JSON.parse(options.body)));

  const result = await saveResearchReview();

  assert.equal(result.status, 'saved');
  assert.equal(toasts.at(-1), 'Đã lưu rà soát cho 1 ảnh bên trái.');
  assert.doesNotMatch(toasts.at(-1), /hai bên/);
});

test('review save localizes browser transport failures and gives retry guidance', async () => {
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };

  const result = await saveResearchReview();

  assert.equal(result.status, 'failed');
  assert.doesNotMatch(result.message, /Failed to fetch/);
  assert.match(result.message, /Không thể kết nối máy chủ.*thử lại/i);
  assert.equal(toasts.at(-1), result.message);
});
const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
const ack = body => ({ status: 'SUCCESS', study_id: body.study_id, review_revision: body.expected_revision + 1,
  reviews: body.reviews.map(row => ({ image_id: row.image_id, prediction_id: row.prediction_id,
    doctor_action: row.doctor_action, review_id: 'review-' + row.image_id })) });

test('unseen/offline gates do not POST, and failed save keeps dirty draft for idempotent retry', async () => {
  const payloads = [];
  globalThis.fetch = async (_url, options) => { payloads.push(JSON.parse(options.body)); return response({ detail: 'synthetic failure' }, 503); };
  state.case.images[1].seen = false;
  assert.equal((await saveResearchReview()).reason, 'unseen-image');
  state.case.images[1].seen = true; navigator.onLine = false;
  assert.equal((await saveResearchReview()).status, 'offline');
  assert.equal(payloads.length, 0);
  navigator.onLine = true;
  assert.equal((await saveResearchReview()).status, 'failed');
  assert.equal(state.dirty, true); assert.equal(removals, 0); assert.equal(state.case.review_revision, 0);
  globalThis.fetch = async (_url, options) => { const body = JSON.parse(options.body); payloads.push(body); return response(ack(body)); };
  assert.deepEqual(await saveResearchReview(), { status: 'saved', studyId: 'study', revision: 1, clean: true });
  assert.equal(payloads[0].request_id, payloads[1].request_id);
  assert.deepEqual(payloads[0].reviews, payloads[1].reviews);
  assert.equal(removals, 3);
  assert.deepEqual(removedKeys, [
    'ova.draft.live.user.study',
    maskDraftKey('study', 'L'),
    maskDraftKey('study', 'R'),
  ]);
});

test('an incomplete ACK cannot advance revision or clear the draft', async () => {
  globalThis.fetch = async (_url, options) => {
    const result = ack(JSON.parse(options.body)); result.reviews[1] = result.reviews[0]; return response(result);
  };
  assert.equal((await saveResearchReview()).status, 'failed');
  assert.equal(state.case.review_revision, 0); assert.equal(state.dirty, true); assert.equal(removals, 0);
});

test('new mask/text edits during an acknowledged save remain dirty', async () => {
  let release, notify;
  const started = new Promise(resolve => { notify = resolve; });
  globalThis.fetch = async (_url, options) => { const body = JSON.parse(options.body); notify(); return new Promise(resolve => { release = () => resolve(response(ack(body))); }); };
  const saving = saveResearchReview(); await started;
  state.case.images[0].mask[50] = 1; state.case.images[0].notes = 'new after snapshot'; release();
  const result = await saving;
  assert.equal(result.status, 'saved'); assert.equal(result.clean, false);
  assert.equal(state.dirty, true); assert.equal(removals, 0);
  assert.equal(state.case.images[0].review.clinical_notes, '');
  assert.equal(state.case.images[0].notes, 'new after snapshot');
});

test('a committed save remains acknowledged if removing a local draft fails', async () => {
  globalThis.localStorage.removeItem = () => { throw new DOMException('denied', 'SecurityError'); };
  globalThis.fetch = async (_url, options) => response(ack(JSON.parse(options.body)));
  const result = await saveResearchReview();
  assert.equal(result.status, 'saved'); assert.equal(result.clean, true);
  assert.equal(state.case.review_revision, 1);
});

test('a save response from a previous token cannot mark the current session saved', async () => {
  globalThis.fetch = async (_url, options) => { const body = JSON.parse(options.body); state.token = 'another-token'; return response(ack(body)); };
  assert.equal((await saveResearchReview()).status, 'failed');
  assert.equal(state.case.review_revision, 0); assert.equal(state.dirty, true); assert.equal(removals, 0);
});

test('review saves broadcast busy start and finish to disable viewer actions', async () => {
  let release, notify;
  const started = new Promise(resolve => { notify = resolve; });
  globalThis.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    notify();
    return new Promise(resolve => { release = () => resolve(response(ack(body))); });
  };
  const saving = saveResearchReview();
  await started;
  assert.equal(state.busy, true);
  assert.deepEqual(busyTransitions, [true]);
  release();
  await saving;
  assert.equal(state.busy, false);
  assert.deepEqual(busyTransitions, [true, false]);
});

test('server-confirmed review unlocks while telemetry flush is still pending', async () => {
  let flushCount = 0;
  let notifyTelemetryFlush;
  let releaseTelemetryFlush;
  const telemetryFlushStarted = new Promise(resolve => { notifyTelemetryFlush = resolve; });
  const telemetryFlushPending = new Promise(resolve => { releaseTelemetryFlush = resolve; });
  Object.assign(tracker, {
    getStudyId: () => 'study',
    getSessionId: () => 'hitl-session',
    flush: async () => {
      flushCount += 1;
      if (flushCount === 1) return { complete: false };
      notifyTelemetryFlush();
      return telemetryFlushPending;
    },
  });
  globalThis.fetch = async (_url, options) => response(ack(JSON.parse(options.body)));

  const saving = saveResearchReview();
  await telemetryFlushStarted;
  const pendingState = {
    busy: state.busy,
    dirty: state.dirty,
    reviewRevision: state.case.review_revision,
    pendingTelemetryStudy: state.pendingReviewTelemetryAck?.studyId,
    pendingTelemetrySession: state.pendingReviewTelemetryAck?.sessionId,
  };
  const completedBeforeTelemetry = await Promise.race([
    saving.then(result => ({ result })),
    new Promise(resolve => realTimeout(() => resolve({ timedOut: true }), 50)),
  ]);
  releaseTelemetryFlush({ complete: true });
  const result = completedBeforeTelemetry.result || await saving;

  assert.deepEqual(pendingState, {
    busy: false,
    dirty: false,
    reviewRevision: 1,
    pendingTelemetryStudy: 'study',
    pendingTelemetrySession: 'hitl-session',
  });
  assert.equal(completedBeforeTelemetry.timedOut, undefined,
    'The successful clinical save must not wait for a delayed non-clinical telemetry request.');
  assert.deepEqual(result, { status: 'saved', studyId: 'study', revision: 1, clean: true });
  assert.equal(state.busy, false);
  await new Promise(resolve => realTimeout(resolve, 0));
  assert.equal(state.pendingReviewTelemetryAck, null,
    'The background telemetry acknowledgement clears only after its flush succeeds.');
});

test('telemetry failure keeps its ACK retryable without repeating the committed review write', async () => {
  let flushCount = 0;
  let notifyTelemetryFlush;
  let rejectTelemetryFlush;
  const telemetryFlushStarted = new Promise(resolve => { notifyTelemetryFlush = resolve; });
  const telemetryFlushPending = new Promise((_resolve, reject) => { rejectTelemetryFlush = reject; });
  let reviewWrites = 0;
  Object.assign(tracker, {
    getStudyId: () => 'study',
    getSessionId: () => 'hitl-session',
    flush: async () => {
      flushCount += 1;
      if (flushCount === 1) return { complete: false };
      if (flushCount === 2) {
        notifyTelemetryFlush();
        return telemetryFlushPending;
      }
      return { complete: true };
    },
  });
  globalThis.fetch = async (_url, options) => {
    reviewWrites += 1;
    return response(ack(JSON.parse(options.body)));
  };

  const saving = saveResearchReview();
  await telemetryFlushStarted;
  const result = await saving;
  assert.equal(result.status, 'saved');
  assert.equal(state.busy, false);
  assert.equal(state.pendingReviewTelemetryAck?.studyId, 'study');
  rejectTelemetryFlush(new Error('synthetic telemetry outage'));
  await new Promise(resolve => realTimeout(resolve, 0));

  assert.equal(state.pendingReviewTelemetryAck?.sessionId, 'hitl-session');
  assert.equal(state.case.review_revision, 1);
  assert.equal(state.dirty, false);
  assert.equal(reviewWrites, 1);
  const retried = await saveResearchReview();
  assert.equal(retried.status, 'saved');
  assert.equal(state.pendingReviewTelemetryAck, null);
  assert.equal(state.busy, false);
  assert.equal(reviewWrites, 1,
    'Retrying telemetry must not send the already committed clinical review a second time.');
  assert.equal(flushCount, 3);
});
