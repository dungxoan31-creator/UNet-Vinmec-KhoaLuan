let defaultRequest = null;
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
} = {}) {
  const activeRequest = request || (async (...args) => {
    const fn = await getDefaultRequest();
    return fn(...args);
  });
  let sessionId = null;
  let studyId = null;
  let sessionStartTime = 0;
  let eventQueue = [];
  let isFlushing = false;
  const tasks = new Map();

  function getSessionId() {
    return sessionId;
  }

  function getStudyId() {
    return studyId;
  }

  function reset() {
    sessionId = null;
    studyId = null;
    sessionStartTime = 0;
    eventQueue = [];
    tasks.clear();
  }

  async function startSession(newStudyId, participantMetadata = {}) {
    studyId = newStudyId;
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
    });

    sessionId = res.id;
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
      payload: payload && Object.keys(payload).length > 0 ? payload : undefined,
    };

    task.events.push(event);
    eventQueue.push(event);
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

  function commitEdit(imageId, { tool = "brush", changed_pixels = 0 } = {}) {
    const task = tasks.get(imageId);
    if (!task) return;
    const currentTime = now();
    if (task.activeStrokeStart != null) {
      task.activeEditMs += Math.max(0, currentTime - task.activeStrokeStart);
      task.activeStrokeStart = null;
    }
    task.editCount += 1;
    track(imageId, "EDIT_COMMITTED", { tool, changed_pixels });
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
      if (!task.completed || task.saveFailed) return false;
    }
    return true;
  }

  async function flush() {
    if (!sessionId || eventQueue.length === 0 || isFlushing) {
      return { complete: isComplete() };
    }

    isFlushing = true;
    try {
      while (eventQueue.length > 0) {
        const batch = eventQueue.slice(0, 100);
        await activeRequest(`/api/hitl/sessions/${sessionId}/events`, {
          method: "POST",
          body: { events: batch },
        });
        eventQueue.splice(0, batch.length);
      }
    } finally {
      isFlushing = false;
    }
    return { complete: isComplete() };
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
