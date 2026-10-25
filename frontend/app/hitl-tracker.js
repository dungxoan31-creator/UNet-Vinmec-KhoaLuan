let defaultRequest = null;
const OUTBOX_STORAGE_KEY = "ova.hitl.outbox.v1";

function getSessionStorage() {
  try {
    return typeof sessionStorage !== "undefined" ? sessionStorage : null;
  } catch {
    return null;
  }
}

const SAFE_ERROR_TYPES = new Set([
  "AbortError",
  "ApiError",
  "Error",
  "NetworkError",
  "RangeError",
  "SyntaxError",
  "TimeoutError",
  "TypeError",
]);
const SAFE_EDIT_TOOLS = new Set([
  "brush",
  "candidate_apply",
  "clear",
  "erase",
  "fill",
  "polygon",
  "redo",
  "reset",
  "small",
  "smooth",
  "undo",
]);
const SAFE_SOURCE_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const SAFE_MODEL_VERSION = /^[A-Za-z0-9][A-Za-z0-9._:+-]{0,99}$/;

function addCandidateProvenance(result, payload) {
  if (payload.tool !== "candidate_apply") return;
  const hasFlatProvenance = payload.candidate_algorithm !== undefined;
  const parameters = payload.candidate_parameters || (hasFlatProvenance ? {
    min_component_area: payload.candidate_min_component_area,
    closing_kernel_size: payload.candidate_closing_kernel_size,
    fill_holes: payload.candidate_fill_holes,
    smoothing_kernel_size: payload.candidate_smoothing_kernel_size,
  } : null);
  const provenance = payload.candidate_provenance || (hasFlatProvenance ? {
    algorithm: payload.candidate_algorithm,
    algorithm_version: payload.candidate_algorithm_version,
    prediction_id: payload.candidate_prediction_id,
    model_version: payload.candidate_model_version,
    checkpoint_sha256: payload.candidate_checkpoint_sha256,
  } : null);
  if (!parameters || typeof parameters !== "object" || Array.isArray(parameters) ||
      !provenance || typeof provenance !== "object" || Array.isArray(provenance)) return;

  const validKernel = (value, { allowZero = false, allowNull = false } = {}) =>
    (allowNull && value === null) || (allowZero && value === 0) ||
    (Number.isInteger(value) && value >= 3 && value <= 31 && value % 2 === 1);
  if (
    !Number.isInteger(parameters.min_component_area) ||
    parameters.min_component_area < 0 || parameters.min_component_area > 512 * 512 ||
    !validKernel(parameters.closing_kernel_size, { allowZero: true }) ||
    typeof parameters.fill_holes !== "boolean" ||
    !validKernel(parameters.smoothing_kernel_size, { allowNull: true }) ||
    provenance.algorithm !== "explicit_morphology_candidate" ||
    provenance.algorithm_version !== "1.0.0" ||
    typeof provenance.prediction_id !== "string" ||
    !SAFE_SOURCE_ID.test(provenance.prediction_id)
  ) return;

  result.candidate_algorithm = provenance.algorithm;
  result.candidate_algorithm_version = provenance.algorithm_version;
  result.candidate_prediction_id = provenance.prediction_id;
  result.candidate_min_component_area = parameters.min_component_area;
  result.candidate_closing_kernel_size = parameters.closing_kernel_size;
  result.candidate_fill_holes = parameters.fill_holes;
  result.candidate_smoothing_kernel_size = parameters.smoothing_kernel_size;
  if (typeof provenance.model_version === "string" && SAFE_MODEL_VERSION.test(provenance.model_version))
    result.candidate_model_version = provenance.model_version;
  if (typeof provenance.checkpoint_sha256 === "string" && /^[0-9a-f]{64}$/i.test(provenance.checkpoint_sha256))
    result.candidate_checkpoint_sha256 = provenance.checkpoint_sha256.toLowerCase();
}

function sanitizeEventPayload(eventType, payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return undefined;

  if (eventType === "SAVE_FAILED" || eventType === "INFERENCE_FAILED") {
    const result = {};
    if (SAFE_ERROR_TYPES.has(payload.error_type)) result.error_type = payload.error_type;
    if (Number.isInteger(payload.http_status) && payload.http_status >= 0 && payload.http_status <= 599)
      result.http_status = payload.http_status;
    return Object.keys(result).length ? result : undefined;
  }

  if (eventType === "EDIT_COMMITTED") {
    const result = {};
    if (SAFE_EDIT_TOOLS.has(payload.tool)) result.tool = payload.tool;
    if (Number.isInteger(payload.changed_pixels) && payload.changed_pixels >= 0 && payload.changed_pixels <= 512 * 512)
      result.changed_pixels = payload.changed_pixels;
    addCandidateProvenance(result, payload);
    return Object.keys(result).length ? result : undefined;
  }

  if (eventType === "CONFIRM_ACK" && typeof payload.batch_request_id === "string" && /^[A-Za-z0-9._-]{1,64}$/.test(payload.batch_request_id))
    return { batch_request_id: payload.batch_request_id };

  if (eventType === "SESSION_ABORTED") {
    const reasons = new Set(["user_navigated_away", "lease_lost", "route_changed", "session_expired"]);
    return { reason: reasons.has(payload.reason) ? payload.reason : "other" };
  }

  return undefined;
}

async function getDefaultRequest() {
  if (!defaultRequest) {
    const mod = await import("./api.js");
    defaultRequest = mod.request;
  }
  return defaultRequest;
}

function generateUUID() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function createTracker({
  now = typeof performance !== "undefined" && performance.now
    ? () => performance.now()
    : () => Date.now(),
  utc = () => new Date().toISOString(),
  request = null,
  storage = getSessionStorage(),
} = {}) {
  const activeRequest = request || (async (...args) => {
    const fn = await getDefaultRequest();
    return fn(...args);
  });
  let sessionId = null;
  let studyId = null;
  let sessionHeaders = {};
  let sessionStartTime = 0;
  let eventQueue = [];
  const flushPromises = new Map();
  let activeOwnerId = null;
  let outboxStorageWarningShown = false;
  const tasks = new Map();
  const outbox = new Map();

  function warnOutboxStorageUnavailable(error = null) {
    if (outboxStorageWarningShown || typeof window === "undefined") return;
    outboxStorageWarningShown = true;
    console.warn("HITL telemetry could not be saved to tab storage.", error);
    window.dispatchEvent(new Event("ova:hitl-storage-error"));
  }

  function isStoredEvent(event) {
    return (
      event &&
      typeof event === "object" &&
      typeof event.event_id === "string" &&
      typeof event.task_id === "string" &&
      typeof event.image_id === "string" &&
      typeof event.event_type === "string" &&
      Number.isInteger(event.seq) &&
      typeof event.client_utc === "string" &&
      Number.isFinite(event.elapsed_ms) &&
      Number.isFinite(event.session_elapsed_ms)
    );
  }

  function readOutbox() {
    if (!storage) return;
    try {
      const raw = storage.getItem(OUTBOX_STORAGE_KEY);
      if (!raw) return;
      const records = JSON.parse(raw);
      if (!Array.isArray(records)) throw new TypeError("HITL outbox must be an array");
      let sanitized = false;
      for (const record of records) {
        if (
          record &&
          typeof record.sessionId === "string" &&
          typeof record.studyId === "string" &&
          (record.ownerId == null || typeof record.ownerId === "string") &&
          Array.isArray(record.events) &&
          record.events.length > 0 &&
          record.events.every(isStoredEvent)
        ) {
          const events = record.events.map((event) => {
            const payload = sanitizeEventPayload(event.event_type, event.payload);
            if (JSON.stringify(payload) !== JSON.stringify(event.payload)) sanitized = true;
            const safeEvent = { ...event };
            if (payload === undefined) delete safeEvent.payload;
            else safeEvent.payload = payload;
            return safeEvent;
          });
          outbox.set(record.sessionId, { ...record, events });
        }
      }
      if (sanitized) writeOutbox();
    } catch (error) {
      try {
        storage.removeItem(OUTBOX_STORAGE_KEY);
      } catch {
        // Storage can be unavailable even for cleanup.
      }
      console.warn("Discarded unreadable HITL telemetry outbox.", error);
    }
  }

  function writeOutbox() {
    if (!storage) {
      warnOutboxStorageUnavailable();
      return false;
    }
    try {
      if (outbox.size === 0) storage.removeItem(OUTBOX_STORAGE_KEY);
      else storage.setItem(OUTBOX_STORAGE_KEY, JSON.stringify([...outbox.values()]));
      return true;
    } catch (error) {
      warnOutboxStorageUnavailable(error);
      return false;
    }
  }

  function persistQueue(targetSessionId, targetStudyId, ownerId, queue) {
    if (!targetSessionId || !targetStudyId) return;
    if (queue.length === 0) {
      if (outbox.delete(targetSessionId)) writeOutbox();
      return;
    }
    outbox.set(targetSessionId, {
      sessionId: targetSessionId,
      studyId: targetStudyId,
      ownerId,
      events: [...queue],
    });
    writeOutbox();
  }

  function persistActiveQueue() {
    persistQueue(sessionId, studyId, activeOwnerId, eventQueue);
  }

  readOutbox();

  function getSessionId() {
    return sessionId;
  }

  function getStudyId() {
    return studyId;
  }

  function reset() {
    persistActiveQueue();
    sessionId = null;
    studyId = null;
    activeOwnerId = null;
    sessionHeaders = {};
    sessionStartTime = 0;
    eventQueue = [];
    tasks.clear();
  }

  async function startSession(newStudyId, participantMetadata = {}, headers = {}) {
    persistActiveQueue();
    sessionId = null;
    studyId = newStudyId;
    activeOwnerId = participantMetadata.local_owner_id ?? null;
    sessionHeaders = { ...headers };
    sessionStartTime = now();
    eventQueue = [];
    tasks.clear();

    const body = {
      study_id: studyId,
      participant_code: participantMetadata.participant_code || "ANONYMOUS",
      participant_role: participantMetadata.participant_role || "technical_tester",
      data_origin: participantMetadata.data_origin || "live",
    };

    const res = await activeRequest("/api/hitl/sessions", {
      method: "POST",
      body,
      headers: sessionHeaders,
    });

    sessionId = res.id;
    persistActiveQueue();
    return res;
  }

  function startTask(imageId, predictionId = null) {
    const taskId = generateUUID();
    const taskStartTime = now();
    const task = {
      taskId,
      imageId,
      predictionId,
      taskStartTime,
      seq: 0,
      events: [],
      activeStrokeStart: null,
      activeEditMs: 0,
      inferenceStart: null,
      inferenceEnd: null,
      roundtripMs: 0,
      viewedTime: null,
      firstEditTime: null,
      confirmAttemptTime: null,
      confirmAckTime: null,
      pauseStartTime: null,
      pausedMs: 0,
      editCount: 0,
      resetCount: 0,
      saveFailed: false,
      completed: false,
    };
    tasks.set(imageId, task);
    return taskId;
  }

  function getTask(imageId) {
    return tasks.get(imageId);
  }

  function track(imageId, eventType, payload = {}) {
    const task = tasks.get(imageId);
    if (!task) return null;

    task.seq += 1;
    const currentTime = now();
    const elapsedMs = Math.max(0, currentTime - task.taskStartTime);
    const sessionElapsedMs = Math.max(0, currentTime - sessionStartTime);

    // Timeline bookkeeping
    if (eventType === "INFERENCE_START") {
      task.inferenceStart = currentTime;
    } else if (eventType === "INFERENCE_END") {
      task.inferenceEnd = currentTime;
      if (task.inferenceStart != null) {
        task.roundtripMs = Math.max(0, task.inferenceEnd - task.inferenceStart);
      }
    } else if (eventType === "PREDICTION_VIEWED") {
      task.viewedTime = currentTime;
    } else if (eventType === "CONFIRM_ATTEMPT") {
      task.confirmAttemptTime = currentTime;
    } else if (eventType === "RESET_AI") {
      task.resetCount += 1;
    }

    const event = {
      event_id: generateUUID(),
      task_id: task.taskId,
      image_id: imageId,
      prediction_id: task.predictionId,
      seq: task.seq,
      event_type: eventType,
      client_utc: utc(),
      elapsed_ms: Number(elapsedMs.toFixed(2)),
      session_elapsed_ms: Number(sessionElapsedMs.toFixed(2)),
      payload: sanitizeEventPayload(eventType, payload),
    };

    task.events.push(event);
    eventQueue.push(event);
    persistActiveQueue();
    return event;
  }

  function startStroke(imageId) {
    const task = tasks.get(imageId);
    if (!task) return;
    if (task.firstEditTime == null) {
      task.firstEditTime = now();
      track(imageId, "CORRECTION_START");
    }
    task.activeStrokeStart = now();
  }

  function commitEdit(imageId, {
    tool = "brush",
    changed_pixels = 0,
    candidate_parameters = null,
    candidate_provenance = null,
  } = {}) {
    const task = tasks.get(imageId);
    if (!task) return;
    const currentTime = now();
    if (task.activeStrokeStart != null) {
      task.activeEditMs += Math.max(0, currentTime - task.activeStrokeStart);
      task.activeStrokeStart = null;
    }
    task.editCount += 1;
    track(imageId, "EDIT_COMMITTED", {
      tool,
      changed_pixels,
      candidate_parameters,
      candidate_provenance,
    });
  }

  function recordPause(imageId) {
    const task = tasks.get(imageId);
    if (!task) return;
    task.pauseStartTime = now();
    track(imageId, "PAUSE");
  }

  function recordResume(imageId) {
    const task = tasks.get(imageId);
    if (!task) return;
    if (task.pauseStartTime != null) {
      task.pausedMs += Math.max(0, now() - task.pauseStartTime);
      task.pauseStartTime = null;
    }
    track(imageId, "RESUME");
  }

  function recordSaveFailure(imageId, payload = {}) {
    const task = tasks.get(imageId);
    if (task) {
      task.saveFailed = true;
    }
    track(imageId, "SAVE_FAILED", payload);
  }

  function confirmAck(imageId, batchRequestId, options = {}) {
    if (options.targetSessionId && options.targetSessionId !== sessionId) {
      return null;
    }
    const task = tasks.get(imageId);
    if (!task) return null;

    task.confirmAckTime = now();
    task.completed = true;
    return track(imageId, "CONFIRM_ACK", { batch_request_id: batchRequestId });
  }

  function getWatermarks() {
    const list = [];
    for (const task of tasks.values()) {
      list.push({
        task_id: task.taskId,
        last_seq: task.seq,
      });
    }
    return list;
  }

  function getTaskMetrics(imageId) {
    const task = tasks.get(imageId);
    if (!task) return null;

    const roundtrip = task.roundtripMs;
    const activeEdit = task.activeEditMs;
    const reviewElapsed =
      task.viewedTime != null && task.confirmAckTime != null
        ? Math.max(0, task.confirmAckTime - task.viewedTime)
        : 0;
    const correctionElapsed =
      task.firstEditTime != null && task.confirmAttemptTime != null
        ? Math.max(0, task.confirmAttemptTime - task.firstEditTime)
        : 0;
    const taskTotal =
      task.confirmAckTime != null
        ? Math.max(0, task.confirmAckTime - task.taskStartTime)
        : Math.max(0, now() - task.taskStartTime);

    return {
      roundtrip_ms: Math.round(roundtrip),
      active_edit_ms: Math.round(activeEdit),
      review_elapsed_ms: Math.round(reviewElapsed),
      correction_elapsed_ms: Math.round(correctionElapsed),
      task_total_ms: Math.round(taskTotal),
      edit_count: task.editCount,
      reset_count: task.resetCount,
      paused_ms: Math.round(task.pausedMs),
      save_failed: task.saveFailed,
      is_raw_accepted: task.editCount === 0 && task.resetCount === 0,
    };
  }

  function getTaskEvents(imageId) {
    const task = tasks.get(imageId);
    return task ? [...task.events] : [];
  }

  function getQueueLength() {
    return eventQueue.length;
  }

  function isComplete() {
    if (tasks.size === 0) return false;
    for (const task of tasks.values()) {
      if (!task.completed) return false;
    }
    return true;
  }

  async function flush() {
    const flushingSessionId = sessionId;
    const flushingStudyId = studyId;
    const flushingOwnerId = activeOwnerId;
    const flushingQueue = eventQueue;
    const flushingHeaders = { ...sessionHeaders };
    if (!flushingSessionId || flushingQueue.length === 0)
      return { complete: isComplete() };

    const existingFlush = flushPromises.get(flushingSessionId);
    if (existingFlush) {
      await existingFlush;
      if (
        sessionId === flushingSessionId &&
        eventQueue === flushingQueue &&
        flushingQueue.length > 0
      )
        return flush();
      return { complete: isComplete() };
    }

    const flushPromise = (async () => {
      while (flushingQueue.length > 0) {
        const batch = flushingQueue.slice(0, 100);
        await activeRequest(`/api/hitl/sessions/${encodeURIComponent(flushingSessionId)}/events`, {
          method: "POST",
          body: { events: batch },
          headers: flushingHeaders,
        });
        flushingQueue.splice(0, batch.length);
        persistQueue(flushingSessionId, flushingStudyId, flushingOwnerId, flushingQueue);
      }
    })();
    flushPromises.set(flushingSessionId, flushPromise);
    try {
      await flushPromise;
    } finally {
      if (flushPromises.get(flushingSessionId) === flushPromise)
        flushPromises.delete(flushingSessionId);
    }
    return { complete: isComplete() };
  }

  async function flushPendingEvents(targetStudyId, headers = {}, ownerId = null) {
    let replayedEventCount = 0;
    let skippedSessionCount = 0;

    if (sessionId && studyId === targetStudyId && activeOwnerId === ownerId) {
      sessionHeaders = { ...headers };
      await flush();
    }

    for (const record of [...outbox.values()]) {
      if (record.studyId !== targetStudyId) continue;
      if (record.ownerId !== ownerId) {
        skippedSessionCount += 1;
        continue;
      }

      while (record.events.length > 0) {
        const batch = record.events.slice(0, 100);
        await activeRequest(`/api/hitl/sessions/${encodeURIComponent(record.sessionId)}/events`, {
          method: "POST",
          body: { events: batch },
          headers,
        });
        record.events.splice(0, batch.length);
        replayedEventCount += batch.length;
        if (record.events.length === 0) outbox.delete(record.sessionId);
        writeOutbox();
      }
    }

    return { replayedEventCount, skippedSessionCount };
  }

  async function abortSession(reason = "user_navigated_away") {
    if (!sessionId) return;
    for (const imageId of tasks.keys()) {
      track(imageId, "SESSION_ABORTED", { reason });
    }
    await flush();
  }

  return {
    getSessionId,
    getStudyId,
    flushPendingEvents,
    reset,
    startSession,
    startTask,
    getTask,
    track,
    startStroke,
    commitEdit,
    recordPause,
    recordResume,
    recordSaveFailure,
    confirmAck,
    getWatermarks,
    getTaskMetrics,
    getTaskEvents,
    getQueueLength,
    isComplete,
    flush,
    abortSession,
  };
}

export const tracker = createTracker();

let uiQueue = [];
let uiFlushTimer = null;

export function trackUIEvent(caseId, event, payload = {}) {
  uiQueue.push({
    case_id: caseId || null,
    event,
    t_ms: Date.now(),
    payload: payload || {},
  });
  if (uiQueue.length >= 25) {
    flushUIEvents();
  } else if (!uiFlushTimer) {
    uiFlushTimer = setTimeout(flushUIEvents, 5000);
  }
}

export async function flushUIEvents() {
  if (uiFlushTimer) {
    clearTimeout(uiFlushTimer);
    uiFlushTimer = null;
  }
  if (!uiQueue.length) return;
  const batch = uiQueue.splice(0, uiQueue.length);
  try {
    const activeRequest = defaultRequest || (await import("./api.js")).request;
    await activeRequest("/api/hitl/events", {
      method: "POST",
      body: { events: batch },
    });
  } catch {
    uiQueue = [...batch.slice(-50), ...uiQueue].slice(0, 100);
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("pagehide", () => {
    if (!uiQueue.length) return;
    const batch = uiQueue.splice(0, uiQueue.length);
    try {
      const payload = JSON.stringify({ events: batch });
      if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/hitl/events", new Blob([payload], { type: "application/json" }));
      } else {
        fetch("/api/hitl/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
        }).catch(() => {});
      }
    } catch {}
  });
}
