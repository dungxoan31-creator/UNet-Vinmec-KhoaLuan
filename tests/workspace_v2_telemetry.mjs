/**
 * Unit tests for Workspace 2.0 HITL Telemetry Tracker (Task 13).
 */
import assert from "node:assert/strict";

async function run() {
  const { createTracker } = await import("../frontend/app/hitl-tracker.js");

  // Helper for mock clock and mock API
  function createMockEnvironment() {
    let currentMs = 0;
    const now = () => currentMs;
    const utc = () => new Date(1760616000000 + currentMs).toISOString();

    const networkLog = [];
    let nextSessionId = "sess-mock-001";

    const request = async (path, options = {}) => {
      networkLog.push({ path, options, t: currentMs });
      if (path === "/api/hitl/sessions") {
        return {
          id: nextSessionId,
          study_id: options.body?.study_id,
          status: "IN_PROGRESS",
          created_at: utc(),
        };
      }
      if (path.includes("/events")) {
        const events = options.body?.events || [];
        return {
          status: "SUCCESS",
          accepted_count: events.length,
          duplicate_count: 0,
        };
      }
      return { status: "OK" };
    };

    return {
      now,
      utc,
      advance: (ms) => { currentMs += ms; },
      setMs: (ms) => { currentMs = ms; },
      getMs: () => currentMs,
      request,
      networkLog,
      setSessionId: (id) => { nextSessionId = id; },
    };
  }

  console.log("Running Workspace v2 Telemetry Tests...");

  // Test 1: timing_and_edit_counts_are_exact
  {
    const env = createMockEnvironment();
    const tracker = createTracker({ now: env.now, utc: env.utc, request: env.request });

    env.setMs(0);
    const sess = await tracker.startSession("study-001", {
      participant_code: "CLINICIAN_01",
      participant_role: "clinician",
      data_origin: "live",
    });
    assert.equal(sess.id, "sess-mock-001");

    const imgId = "img-left-001";
    const predId = "pred-001";
    tracker.startTask(imgId, predId);

    // Timeline per spec:
    // start 0
    // inference start 10 / end 110 (roundtrip 100)
    env.setMs(10);
    tracker.track(imgId, "INFERENCE_START");
    env.setMs(110);
    tracker.track(imgId, "INFERENCE_END");

    // viewed 120
    env.setMs(120);
    tracker.track(imgId, "PREDICTION_VIEWED");

    // stroke 200–240
    env.setMs(200);
    tracker.startStroke(imgId);
    env.setMs(240);
    tracker.commitEdit(imgId, { tool: "brush", changed_pixels: 120 });

    // confirm attempt 700 / ack 750
    env.setMs(700);
    tracker.track(imgId, "CONFIRM_ATTEMPT");

    env.setMs(750);
    tracker.confirmAck(imgId, "req-batch-123");

    const m = tracker.getTaskMetrics(imgId);
    assert.equal(m.roundtrip_ms, 100, `Expected roundtrip 100ms, got ${m.roundtrip_ms}`);
    assert.equal(m.active_edit_ms, 40, `Expected active edit 40ms, got ${m.active_edit_ms}`);
    assert.equal(m.review_elapsed_ms, 630, `Expected review elapsed 630ms, got ${m.review_elapsed_ms}`);
    assert.equal(m.correction_elapsed_ms, 500, `Expected correction elapsed 500ms, got ${m.correction_elapsed_ms}`);
    assert.equal(m.task_total_ms, 750, `Expected task total 750ms, got ${m.task_total_ms}`);
    assert.equal(m.edit_count, 1, `Expected edit count 1, got ${m.edit_count}`);

    console.log("PASS: timing_and_edit_counts_are_exact");
  }

  // Test 2: old_response_cannot_complete_new_session
  {
    const env = createMockEnvironment();
    const tracker = createTracker({ now: env.now, utc: env.utc, request: env.request });

    env.setSessionId("sess-01");
    await tracker.startSession("study-001", { participant_code: "TEST" });
    const imgId = "img-01";
    tracker.startTask(imgId, "pred-01");

    // Start a new session
    env.setSessionId("sess-02");
    await tracker.startSession("study-002", { participant_code: "TEST" });

    // Old response confirmation attempt with old session ID
    const res = tracker.confirmAck(imgId, "old-req-id", { targetSessionId: "sess-01" });
    assert.equal(tracker.getSessionId(), "sess-02");
    // Completed state of active session is unchanged
    assert.equal(tracker.isComplete(), false);
    console.log("PASS: old_response_cannot_complete_new_session");
  }

  // Test 3: retry_does_not_duplicate_events
  {
    const env = createMockEnvironment();
    const tracker = createTracker({ now: env.now, utc: env.utc, request: env.request });

    await tracker.startSession("study-001", { participant_code: "TEST" });
    const imgId = "img-01";
    tracker.startTask(imgId, "pred-01");

    tracker.track(imgId, "PREDICTION_VIEWED");
    await tracker.flush();

    // After flush, queue should be empty
    assert.equal(tracker.getQueueLength(), 0);

    // Second flush emits nothing
    const netBefore = env.networkLog.length;
    await tracker.flush();
    assert.equal(env.networkLog.length, netBefore);
    console.log("PASS: retry_does_not_duplicate_events");
  }

  // Test 4: reload_starts_new_attempt
  {
    const env = createMockEnvironment();
    const tracker = createTracker({ now: env.now, utc: env.utc, request: env.request });

    env.setMs(100);
    await tracker.startSession("study-001", { participant_code: "TEST" });
    tracker.startTask("img-01", "pred-01");
    env.setMs(500);

    // Simulate page reload by creating new tracker instance
    const tracker2 = createTracker({ now: env.now, utc: env.utc, request: env.request });
    env.setSessionId("sess-new-attempt");
    await tracker2.startSession("study-001", { participant_code: "TEST" });

    assert.notEqual(tracker.getSessionId(), tracker2.getSessionId());
    tracker2.startTask("img-01", "pred-01");
    env.setMs(600);
    tracker2.track("img-01", "PREDICTION_VIEWED");
    const m = tracker2.getTaskMetrics("img-01");
    // New attempt origin is at 500, elapsed is 100
    assert.equal(m.task_total_ms, 100);
    console.log("PASS: reload_starts_new_attempt");
  }

  // Test 5: visibility_pause_is_recorded
  {
    const env = createMockEnvironment();
    const tracker = createTracker({ now: env.now, utc: env.utc, request: env.request });

    await tracker.startSession("study-001", { participant_code: "TEST" });
    const imgId = "img-01";
    tracker.startTask(imgId, "pred-01");

    env.setMs(100);
    tracker.recordPause(imgId);
    env.setMs(5100); // 5000ms pause
    tracker.recordResume(imgId);

    const events = tracker.getTaskEvents(imgId);
    const pauseEv = events.find((e) => e.event_type === "PAUSE");
    const resumeEv = events.find((e) => e.event_type === "RESUME");
    assert.ok(pauseEv, "PAUSE event must be recorded");
    assert.ok(resumeEv, "RESUME event must be recorded");
    assert.equal(tracker.getTaskMetrics(imgId).paused_ms, 5000);
    console.log("PASS: visibility_pause_is_recorded");
  }

  // Test 6: storage_failure_marks_incomplete
  {
    const env = createMockEnvironment();
    const tracker = createTracker({ now: env.now, utc: env.utc, request: env.request });

    await tracker.startSession("study-001", { participant_code: "TEST" });
    const imgId = "img-01";
    tracker.startTask(imgId, "pred-01");

    tracker.recordSaveFailure(imgId, { error: "Network timeout" });
    assert.equal(tracker.isComplete(), false);
    const m = tracker.getTaskMetrics(imgId);
    assert.equal(m.save_failed, true);
    console.log("PASS: storage_failure_marks_incomplete");
  }

  // Test 7: edit_then_reset_is_not_zero_edit_acceptance
  {
    const env = createMockEnvironment();
    const tracker = createTracker({ now: env.now, utc: env.utc, request: env.request });

    await tracker.startSession("study-001", { participant_code: "TEST" });
    const imgId = "img-01";
    tracker.startTask(imgId, "pred-01");

    tracker.startStroke(imgId);
    tracker.commitEdit(imgId, { tool: "eraser", changed_pixels: 50 });
    tracker.track(imgId, "RESET_AI");
    tracker.track(imgId, "CONFIRM_ATTEMPT");
    tracker.confirmAck(imgId, "req-123");

    const m = tracker.getTaskMetrics(imgId);
    assert.equal(m.edit_count, 1, "Edit count must reflect modified stroke before reset");
    assert.equal(m.is_raw_accepted, false, "Edit followed by reset cannot be classified as raw accepted");
    console.log("PASS: edit_then_reset_is_not_zero_edit_acceptance");
  }

  console.log("All Workspace v2 Telemetry Tests passed!");
}

run().catch((e) => {
  console.error("Telemetry test failed:", e);
  process.exitCode = 1;
});
