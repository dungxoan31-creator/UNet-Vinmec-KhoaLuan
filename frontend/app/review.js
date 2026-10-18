import { state, role, clearDraft } from "./state.js";
import { request } from "./api.js";

import { encode } from "./coordinates.js";
import { $, esc, modal, toast } from "./ui.js";
import { tracker } from "./hitl-tracker.js";
export async function saveResearchReview() {
  const c = state.case,
    identity = state.user?.id,
    username = state.user?.username;
  if (
    !c ||
    role() !== "BS" ||
    state.busy ||
    state.editing?.caseId !== c.study_id ||
    !state.editing.allowed ||
    ["LOCKED", "APPROVED", "SIGNED_PRELIM"].includes(c.status)
  )
    return;
  if (c.images.length !== 2 || !c.images.every((i) => i.seen))
    return toast("Xem đủ hai bên trước khi lưu rà soát.", true);
  const manual = c.images.some((i) => !i.prediction?.prediction_id);
  if (manual && !state.capabilities.manual_review)
    return toast(
      "Mask vẽ tay được giữ thành bản nháp. API hiện tại yêu cầu prediction_id; cần API lưu rà soát thủ công để lưu lên máy chủ.",
      true,
    );
  if (!navigator.onLine) {
    state.pendingReview = { caseId: c.study_id, userId: identity };
    return toast(
      "Chưa đồng bộ. Bản rà soát sẽ gửi lại khi có mạng trong phiên này.",
    );
  }
  const snapshots = c.images.map((i) => {
    const tm = tracker.getTaskMetrics(i.image_id);
    const timeSpent =
      tm && tm.task_total_ms > 0 ? Math.round(tm.task_total_ms / 1000) : null;
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
        clinical_notes: i.notes || "",
        lesion_type: i.morphology || "Chưa đánh giá",
        orads: i.orads || "",
        orads_score: i.orads || null,
        morphology_description: i.morphologyDesc || "",
        time_spent_seconds: timeSpent,
      },
    };
  });
  const sameSession = () => state.user?.id === identity && state.case === c;
  const operation = Symbol("review");
  state.operation = operation;
  state.busy = true;
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
    const expectedRevision = c.review_revision ?? 0;
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
        clinical_notes: b.clinical_notes,
        lesion_type: b.lesion_type,
        orads: b.orads,
        morphology_description: b.morphology_description,
      })),
    });

    let requestId = state.currentReviewRequestId;
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

    const hitlSessionId =
      tracker.getStudyId && tracker.getStudyId() === c.study_id
        ? tracker.getSessionId()
        : null;
    const watermarks = hitlSessionId ? tracker.getWatermarks() : [];

    const batchPayload = {
      study_id: c.study_id,
      expected_revision: expectedRevision,
      request_id: requestId,
      reviews: reviewBodies,
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

    if (
      result.status !== "SUCCESS" ||
      !Array.isArray(result.reviews) ||
      result.reviews.length !== c.images.length
    )
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
      };
    }

    if (sameSession()) {
      // FE-01: Compare current clinical fields against submitted snapshot before clearing draft
      const hasPendingChangesAfterSnapshot = c.images.some((img, idx) => {
        const snap = snapshots[idx]?.body;
        if (!snap) return false;
        return (
          (img.orads || "") !== (snap.orads || "") ||
          (img.morphology || "") !== (snap.lesion_type === "Chưa đánh giá" ? "" : (snap.lesion_type || "")) ||
          (img.morphologyDesc || "") !== (snap.morphology_description || "") ||
          (img.notes || "") !== (snap.clinical_notes || "")
        );
      });

      if (!hasPendingChangesAfterSnapshot) {
        clearDraft();
        state.dirty = false;
        state.pendingReview = null;
        state.currentReviewRequestId = null;
        state.lastReviewPayloadSnapshot = null;
        state.lastClinicalSnapshot = null;
        state.lastReviewTimeSpent = null;
        c.status = "REVIEWED";
        toast("Đã lưu rà soát của hai bên thành công.");
      } else {
        // Retain unpersisted edits made after snapshot
        state.dirty = true;
        c.status = "REVIEWED";
        toast("Đã lưu bản rà soát trước đó. Có thay đổi mới chưa lưu.");
      }
    }

    // Telemetry ACK is non-blocking and failure here will not invalidate saved review
    try {
      for (const { image } of snapshots) {
        tracker.confirmAck(image.image_id, requestId);
      }
      await tracker.flush();
    } catch (telemetryErr) {
      console.warn("Telemetry flush warning after successful review commit:", telemetryErr);
    }
  } catch (e) {
    if (e.message && (e.message.includes("409") || e.message.includes("Xung đột phiên bản"))) {
      try {
        const fresh = await request("/api/cases/" + encodeURIComponent(c.study_id));
        if (fresh && fresh.review_revision > expectedRevision) {
          const ourReviews = fresh.images?.filter(
            (img) => img.review?.doctor_id === username,
          );
          if (ourReviews && ourReviews.length === c.images.length) {
            c.review_revision = fresh.review_revision;
            for (const { image } of snapshots) {
              const r = ourReviews.find((revImg) => revImg.image_id === image.image_id)?.review;
              if (r) image.review = r;
            }
            if (sameSession()) {
              clearDraft();
              state.pendingReview = null;
              state.currentReviewRequestId = null;
              state.lastReviewPayloadSnapshot = null;
              state.lastClinicalSnapshot = null;
              state.lastReviewTimeSpent = null;
              c.status = "REVIEWED";
              toast("Đã xác nhận rà soát trên máy chủ thành công.");
              return;
            }
          }
        }
      } catch {
        // Fall back to standard error reporting
      }
    }
    for (const { image } of snapshots || []) {
      tracker.recordSaveFailure(image.image_id, { error: e.message });
    }
    await tracker.flush().catch(() => {});
    toast(e.message, true);
  } finally {
    if (state.operation === operation) state.busy = false;
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
    c.images.length !== 2 ||
    !["L", "R"].every((s) => c.images.some((i) => i.laterality === s && i.seen))
  )
    return toast("Cần xem đủ cả hai ảnh trước khi ký.", true);
  if (["SIGNED_PRELIM", "APPROVED", "LOCKED"].includes(c.status)) return;
  const d = modal(
    "Ký sơ bộ khảo sát hai bên",
    `<p>Kiểm tra mask và ghi chú của cả hai ảnh trước khi chuyển chuyên gia duyệt.</p><div class="grid-2">${c.images.map((i) => `<section class="panel"><div class="panel-body"><h3>Buồng trứng ${i.laterality === "L" ? "trái" : "phải"}</h3><p>${i.mask?.some((v, n) => v !== i.aiMask?.[n]) ? "Mask đã chỉnh sửa" : "Mask AI chưa chỉnh sửa"}</p><p>${esc(i.notes || "Không có ghi chú")}</p><span class="badge">${i.measurements?.calibrated ? "Đã hiệu chuẩn" : "Chưa hiệu chuẩn – chỉ có px"}</span></div></section>`).join("")}</div><details style="margin-top:20px"><summary>Đánh giá nhanh AI (tùy chọn)</summary><label class="field">Mức hữu dụng<select name="rating"><option value="">Bỏ qua</option><option value="5">Hữu ích</option><option value="2">Cần cải thiện</option></select></label><label class="field">Lỗi quan sát<select name="issue"><option value="">Chưa đánh giá</option><option value="FALSE_NEGATIVE">Bỏ sót vùng</option><option value="FALSE_POSITIVE">Lan sang mô lân cận</option><option value="BOUNDARY_MISMATCH">Đường biên chưa khít</option></select></label></details><p class="form-error" id="signError" role="alert"></p><div class="actions"><button class="btn" value="cancel">Tiếp tục rà soát</button><button class="btn primary" type="submit">Ký sơ bộ và chuyển duyệt</button></div>`,
    async (e, dialog) => {
      const btn = e.submitter;
      btn.disabled = true;
      state.busy = true;
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
        state.busy = false;
      }
    },
  );
  return d;
}
