import { state, role, clearDraft, setBusy } from "./state.js";
import { request } from "./api.js";

import { encode } from "./coordinates.js";
import { $, esc, modal, toast } from "./ui.js";
import { tracker } from "./hitl-tracker.js";
import { matchesSubmittedReview, isCompleteReviewAck, hasUnresolvedReviewWarning, clinicianDiagnosisOverrides } from "./review-content.js";
import { formatLaterality } from "./laterality-hint.js";
const blocked = (reason, message) => {
  toast(message, true);
  return { status: "blocked", reason };
};
const notifyReviewDraftStateChanged = () => {
  if (typeof window !== "undefined")
    window.dispatchEvent(new CustomEvent("ova:review-draft-state-changed"));
};

export function savedReviewMessage(images) {
  const entries = Array.isArray(images) ? images : [];
  const sides = new Set(entries.map((image) => image?.laterality).filter((side) => side === "L" || side === "R"));
  const knownSide = sides.size === 1 ? [...sides][0] : null;
  const sideLabel = sides.size === 2
    ? "ở cả hai bên"
    : knownSide && entries.every((image) => image?.laterality === knownSide)
      ? (knownSide === "L" ? "bên trái" : "bên phải")
      : "";
  return `Đã lưu rà soát cho ${entries.length} ảnh${sideLabel ? ` ${sideLabel}` : ""}.`;
}

export async function saveResearchReview() {
  const c = state.case,
    identity = state.user?.id,
    token = state.token,
    username = state.user?.username;
  if (
    !c ||
    role() !== "BS" ||
    state.busy ||
    state.editing?.caseId !== c.study_id ||
    !state.editing.allowed ||
    ["LOCKED", "APPROVED", "SIGNED_PRELIM"].includes(c.status)
  )
    return { status: "blocked", reason: "not-editable" };
  if (!c.images.length || c.images.some(image => !image.seen) ||
      (c.ovary_side === "BOTH" && !["L", "R"].every(side => c.images.some(i => i.laterality === side))))
    return blocked("unseen-image", "Xem toàn bộ ảnh và xác nhận bên khảo sát trước khi lưu rà soát.");
  if (c.images.some(hasUnresolvedReviewWarning))
    return blocked("content-warning", "Kiểm tra cảnh báo mô tả/O-RADS và hoàn tất các chỗ trống trước khi lưu.");
  const manual = c.images.some((i) => !i.prediction?.prediction_id);
  if (manual && !state.capabilities.manual_review)
    return blocked("manual-review-unavailable",
      "Mask vẽ tay được giữ thành bản nháp. API hiện tại yêu cầu prediction_id; cần API lưu rà soát thủ công để lưu lên máy chủ.",
    );
  if (!navigator.onLine) {
    state.pendingReview = { caseId: c.study_id, userId: identity };
    toast(
      "Chưa đồng bộ. Bản rà soát sẽ gửi lại khi có mạng trong phiên này.",
    );
    return { status: "offline", studyId: c.study_id };
  }
  const pendingTelemetryAck = state.pendingReviewTelemetryAck;
  if (pendingTelemetryAck?.studyId === c.study_id && !state.dirty) {
    if (
      tracker.getStudyId?.() !== c.study_id ||
      tracker.getSessionId?.() !== pendingTelemetryAck.sessionId
    ) {
      return blocked("telemetry-session", "Rà soát đã lưu; phiên HITL cũ không còn hoạt động để đồng bộ nhật ký.");
    }
    const operation = Symbol("review-telemetry-retry");
    state.operation = operation;
    setBusy(true);
    try {
      await tracker.flush();
      if (state.pendingReviewTelemetryAck === pendingTelemetryAck)
        state.pendingReviewTelemetryAck = null;
      toast("Đã đồng bộ nhật ký HITL cho rà soát đã lưu.");
    } catch {
      toast("Rà soát đã lưu; nhật ký HITL chưa đồng bộ. Hãy thử lại sau.", true);
    } finally {
      if (state.operation === operation) setBusy(false);
    }
    return { status: "saved", studyId: c.study_id, revision: c.review_revision, clean: !state.dirty };
  }
  const expectedRevision = c.review_revision ?? 0;
  const snapshots = c.images.map((i) => {
    const tm = tracker.getTaskMetrics(i.image_id);
    const timeSpent =
      tm && tm.task_total_ms > 0 ? Math.round(tm.task_total_ms / 1000) : null;
    const clinicianOverrides = clinicianDiagnosisOverrides(i);
    return {
      image: i,
      body: {
        study_id: c.study_id,
        image_id: i.image_id,
        prediction_id: i.prediction?.prediction_id,
        doctor_id: username,
        doctor_action: i.mask.every((v, n) => v === i.aiMask[n])
          ? "ACCEPTED_RAW"
          : i.mask.some(Boolean)
            ? "MODIFIED"
            : "REJECTED_ALL",
        verified_mask_rle: encode(i.mask),
        manual_calipers: i.manualCalipers || [],
        clinical_notes: i.notes || "",
        lesion_type: i.morphology || "Chưa đánh giá",
        orads: i.orads || "",
        orads_score: i.orads || null,
        morphology_description: i.morphologyDesc || "",
        ...(Object.keys(clinicianOverrides).length
          ? { clinician_overrides: clinicianOverrides }
          : {}),
        time_spent_seconds: timeSpent,
      },
    };
  });
  const sameSession = () => state.user?.id === identity && state.token === token && state.case === c;
  const operation = Symbol("review");
  let requestId = null;
  let hitlSessionId = null;
  state.operation = operation;
  setBusy(true);
  const flushReviewAcknowledgements = async () => {
    const pendingAck = hitlSessionId
      ? { studyId: c.study_id, sessionId: hitlSessionId, requestId }
      : null;
    if (pendingAck) state.pendingReviewTelemetryAck = pendingAck;
    try {
      for (const { image } of snapshots) {
        tracker.confirmAck(image.image_id, requestId, { targetSessionId: hitlSessionId });
      }
      await tracker.flush();
      if (state.pendingReviewTelemetryAck === pendingAck)
        state.pendingReviewTelemetryAck = null;
    } catch (telemetryErr) {
      console.warn("Telemetry flush warning after successful review commit:", telemetryErr);
      toast("Đã lưu rà soát. Nhật ký HITL chưa đồng bộ; phiên tham khảo chưa hoàn tất.", true);
    }
  };
  try {
    let manualReviews = null;
    if (manual) {
      const result = await request(
        "/api/workspace/cases/" +
          encodeURIComponent(c.study_id) +
          "/manual-review",
        {
          method: "POST",
          body: { version: c.version, images: snapshots.map((s) => s.body) },
        },
      );
      if (result.status !== "SUCCESS" || !Array.isArray(result.reviews))
        throw Error("Máy chủ chưa xác nhận rà soát thủ công.");
      manualReviews = result.reviews;
    }
    const reviewBodies = snapshots.map((s) => s.body);

    // Fingerprint clinical content (excluding volatile elapsed time)
    const clinicalSnapshot = JSON.stringify({
      study_id: c.study_id,
      expected_revision: expectedRevision,
      reviews: reviewBodies.map((b) => ({
        image_id: b.image_id,
        prediction_id: b.prediction_id,
        doctor_action: b.doctor_action,
        verified_mask_rle: b.verified_mask_rle,
        manual_calipers: b.manual_calipers || [],
        clinical_notes: b.clinical_notes,
        lesion_type: b.lesion_type,
        orads: b.orads,
        morphology_description: b.morphology_description,
        clinician_overrides: b.clinician_overrides || {},
      })),
    });

    requestId = state.currentReviewRequestId;
    let savedTimeSpent = state.lastReviewTimeSpent;
    if (!requestId || state.lastClinicalSnapshot !== clinicalSnapshot) {
      requestId = crypto.randomUUID();
      state.currentReviewRequestId = requestId;
      state.lastClinicalSnapshot = clinicalSnapshot;
      state.lastReviewTimeSpent = reviewBodies.map((b) => b.time_spent_seconds);
    } else if (savedTimeSpent) {
      // Re-use exact same time_spent_seconds for idempotent retry
      reviewBodies.forEach((b, idx) => {
        b.time_spent_seconds = savedTimeSpent[idx];
      });
    }

    if (!sameSession())
      throw Error("Phiên hoặc ca đã thay đổi. Bản nháp cũ được giữ.");

    for (const { image } of snapshots) {
      tracker.track(image.image_id, "CONFIRM_ATTEMPT");
    }
    await tracker.flush();

    hitlSessionId =
      tracker.getStudyId && tracker.getStudyId() === c.study_id
        ? tracker.getSessionId()
        : null;
    const watermarks = hitlSessionId ? tracker.getWatermarks() : [];

    const batchPayload = {
      study_id: c.study_id,
      expected_revision: expectedRevision,
      request_id: requestId,
      reviews: reviewBodies,
      ...(state.editing?.leaseToken
        ? { lease_token: state.editing.leaseToken }
        : {}),
      ...(state.editing?.pageInstanceId
        ? { page_instance_id: state.editing.pageInstanceId }
        : {}),
      ...(hitlSessionId
        ? { hitl_session_id: hitlSessionId, telemetry_tasks: watermarks }
        : {}),
    };

    const result = manualReviews
      ? {
          status: "SUCCESS",
          study_id: c.study_id,
          review_revision: expectedRevision + 1,
          reviews: manualReviews,
        }
      : await request("/api/reviews/batch", {
          method: "POST",
          body: batchPayload,
        });

    if (!isCompleteReviewAck(result, c.study_id, expectedRevision, reviewBodies))
      throw Error("Máy chủ chưa xác nhận toàn bộ bản rà soát.");

    if (!sameSession())
      throw Error("Phiên đã thay đổi sau khi lưu. Mở lại ca để kiểm tra.");

    // Update revision and review record immediately upon successful batch commit
    c.review_revision = result.review_revision;
    for (const { image, body } of snapshots) {
      const rev = result.reviews.find((r) => r.image_id === image.image_id);
      image.review = {
        ...rev,
        doctor_id: username,
        verified_mask_rle: body.verified_mask_rle,
        clinical_notes: body.clinical_notes,
        lesion_type: body.lesion_type,
        orads: body.orads,
        orads_score: body.orads_score,
        morphology_description: body.morphology_description,
        clinician_overrides: body.clinician_overrides || {},
      };
    }
    window.dispatchEvent(new CustomEvent("ova:review-saved", {
      detail: { studyId: c.study_id, imageIds: snapshots.map(({ image }) => image.image_id) },
    }));

    if (sameSession()) {
      // FE-01: Compare current clinical fields against submitted snapshot before clearing draft
      const hasPendingChangesAfterSnapshot = c.images.length !== snapshots.length ||
        snapshots.some(({ image, body }) => !c.images.includes(image) || !matchesSubmittedReview(image, body));

      if (!hasPendingChangesAfterSnapshot) {
        clearDraft();
        state.dirty = false;
        state.pendingReview = null;
        state.currentReviewRequestId = null;
        state.lastReviewPayloadSnapshot = null;
        state.lastClinicalSnapshot = null;
        state.lastReviewTimeSpent = null;
        c.status = "REVIEWED";
        notifyReviewDraftStateChanged();
        toast(savedReviewMessage(snapshots.map(({ image }) => image)));
      } else {
        // Retain unpersisted edits made after snapshot
        state.dirty = true;
        c.status = "REVIEWED";
        notifyReviewDraftStateChanged();
        toast("Đã lưu bản rà soát trước đó. Có thay đổi mới chưa lưu.");
      }
    }

    // The committed review is the clinical write. Keep telemetry queued/retryable
    // without holding the viewer's save lock on a separate network request.
    void flushReviewAcknowledgements();
    return { status: "saved", studyId: c.study_id, revision: c.review_revision, clean: !state.dirty };
  } catch (e) {
    if (e?.status === 409) {
      try {
        const fresh = await request("/api/cases/" + encodeURIComponent(c.study_id));
        const persistedImages = new Map(
          (Array.isArray(fresh?.images) ? fresh.images : []).map((img) => [img.image_id, img]),
        );
        if (
          fresh?.latest_review_request_id === requestId &&
          fresh.review_revision === expectedRevision + 1 &&
          snapshots.every(({ image }) => persistedImages.get(image.image_id)?.review?.doctor_id === username)
        ) {
            c.review_revision = fresh.review_revision;
            for (const { image } of snapshots) {
              image.review = persistedImages.get(image.image_id).review;
            }
            window.dispatchEvent(new CustomEvent("ova:review-saved", {
              detail: { studyId: c.study_id, imageIds: snapshots.map(({ image }) => image.image_id) },
            }));
            if (sameSession()) {
              const clean = c.images.length === snapshots.length && snapshots.every(({ image, body }) =>
                c.images.includes(image) && matchesSubmittedReview(image, body));
              if (clean) clearDraft();
              else state.dirty = true;
              state.pendingReview = null;
              state.currentReviewRequestId = null;
              state.lastReviewPayloadSnapshot = null;
              state.lastClinicalSnapshot = null;
              state.lastReviewTimeSpent = null;
              c.status = "REVIEWED";
              notifyReviewDraftStateChanged();
              toast(savedReviewMessage(snapshots.map(({ image }) => image)));
              void flushReviewAcknowledgements();
              return { status: "saved", studyId: c.study_id, revision: c.review_revision, clean };
            }
        }
      } catch {
        // Fall back to standard error reporting
      }
    }
    for (const { image } of snapshots || []) {
      tracker.recordSaveFailure(image.image_id, {
        error_type: e.name,
        http_status: e.status,
      });
    }
    await tracker.flush().catch(() => {});
    toast(e.message, true);
    return { status: e?.status === 409 ? "conflict" : "failed", studyId: c.study_id, message: e.message };
  } finally {
    if (state.operation === operation) setBusy(false);
  }
}
export function openSignoff() {
  const c = state.case,
    identity = state.user?.id;
  if (state.busy || !state.editing?.allowed) return;
  if (!state.capabilities?.case_workflow)
    return toast("Tính năng quy trình hai cấp (Ký sơ bộ / Chuyển duyệt) chưa được kích hoạt trên hệ thống.", true);
  if (
    role() !== "BS" ||
    !c ||
    !c.images.length ||
    !c.images.every((image) => image.seen) ||
    (c.ovary_side === "BOTH" && !["L", "R"].every((side) => c.images.some((image) => image.laterality === side)))
  )
    return toast("Cần xem toàn bộ ảnh và xác nhận đủ bên của ca trước khi ký.", true);
  if (["SIGNED_PRELIM", "APPROVED", "LOCKED"].includes(c.status)) return;
  const d = modal(
    "Ký sơ bộ khảo sát",
    `<p>Kiểm tra mask và ghi chú của ${c.images.length} ảnh trước khi chuyển chuyên gia duyệt.</p><div class="grid-2">${c.images.map((i, index) => `<section class="panel"><div class="panel-body"><h3>Buồng trứng ${formatLaterality(i.laterality)} · ảnh ${index + 1}</h3><p>${i.mask?.some((v, n) => v !== i.aiMask?.[n]) ? "Mask đã chỉnh sửa" : "Mask AI chưa chỉnh sửa"}</p><p>${esc(i.notes || "Không có ghi chú")}</p>${i.measurements?.calibrated ? '<span class="badge">Đã hiệu chuẩn</span>' : ""}</div></section>`).join("")}</div><details style="margin-top:20px"><summary>Đánh giá nhanh AI (tùy chọn)</summary><label class="field">Mức hữu dụng<select name="rating"><option value="">Bỏ qua</option><option value="5">Hữu ích</option><option value="2">Cần cải thiện</option></select></label><label class="field">Lỗi quan sát<select name="issue"><option value="">Bỏ qua</option><option value="FALSE_NEGATIVE">Bỏ sót vùng</option><option value="FALSE_POSITIVE">Lan sang mô lân cận</option><option value="BOUNDARY_MISMATCH">Đường biên chưa khít</option></select></label></details><p class="form-error" id="signError" role="alert"></p><div class="actions"><button class="btn" value="cancel">Tiếp tục rà soát</button><button class="btn primary" type="submit">Ký sơ bộ và chuyển duyệt</button></div>`,
    async (e, dialog) => {
      const btn = e.submitter;
      btn.disabled = true;
      setBusy(true);
      try {
        const form = Object.fromEntries(new FormData(e.target));
        {
          const body = {
            version: c.version,
            images: c.images.map((i) => ({
              image_id: i.image_id,
              prediction_id: i.prediction?.prediction_id,
              verified_mask_rle: encode(i.mask),
              notes: i.notes,
              morphology: i.morphology,
            })),
            feedback: form.rating
              ? { rating: Number(form.rating), issue: form.issue || null }
              : null,
          };
          const result = await request(
            "/api/workspace/cases/" + c.study_id + "/sign-preliminary",
            { method: "POST", body },
          );
          if (result.status !== "SIGNED_PRELIM")
            throw Error("Máy chủ chưa xác nhận ký sơ bộ.");
          c.status = result.status;
        }
        if (state.user?.id !== identity || state.case !== c)
          throw Error(
            "Phiên hoặc ca đã thay đổi. Mở lại ca để kiểm tra kết quả.",
          );
        clearDraft();
        dialog.close();
        toast("Đã ký sơ bộ và chuyển duyệt.");
        location.hash = "#case/" + c.study_id;
      } catch (err) {
        $("#signError").textContent = err.message;
      } finally {
        btn.disabled = false;
        setBusy(false);
      }
    },
  );
  return d;
}
