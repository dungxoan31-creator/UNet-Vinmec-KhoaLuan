import { state, setBusy } from "./state.js";
import { request, uploadFile } from "./api.js";
import { decode } from "./coordinates.js";
import { $, errorBox, button, toast, modal } from "./ui.js";
import { tracker } from "./hitl-tracker.js";
import { acquireLease } from "./leases.js";
let pending = null;

export async function startBilateral(files, metadata) {
  if (state.busy) return;
  // Keep the legacy single-File contract while allowing ordered image lists per side.
  const imageEntries = Object.fromEntries(["L", "R"].map(side => [
    side,
    (Array.isArray(files?.[side]) ? files[side] : files?.[side] ? [files[side]] : []).map((item, index) => ({
      file: item && typeof item === "object" && "file" in item ? item.file : item,
      dicom: item && typeof item === "object" && "file" in item ? item.dicom : metadata.dicom?.[side],
      intakeKey: item && typeof item === "object" && typeof item.id === "string"
        ? item.id
        : `${item?.name || item?.file?.name || "image"}:${item?.size || item?.file?.size || 0}:${item?.lastModified || item?.file?.lastModified || 0}:${index}`,
      index,
    })),
  ]));
  const uploadSides = ["L", "R"].filter(side => imageEntries[side].length > 0);
  const imageCount = uploadSides.reduce((total, side) => total + imageEntries[side].length, 0);
  const activeOvarySide = metadata.active_ovary_side || (imageEntries.L.length && imageEntries.R.length ? "BOTH" : imageEntries.L.length ? "LEFT" : "RIGHT");
  const contralateralStatus = metadata.contralateral_status ?? (imageEntries.L.length && imageEntries.R.length ? "UNKNOWN" : null);
  if (!uploadSides.length)
    return toast("Cần ít nhất một ảnh buồng trứng trước khi chạy.", true);
  if (uploadSides.length === 1 && !["SURGICALLY_ABSENT", "NOT_VISUALIZED"].includes(contralateralStatus))
    return toast("Cần ghi nhận đúng tình trạng bên không có ảnh trước khi chạy.", true);
  if (imageCount > 40 || ["L", "R"].some(side => imageEntries[side].length > 20))
    return toast("Mỗi bên chỉ được tải tối đa 20 ảnh.", true);
  if (imageEntries.L.concat(imageEntries.R).some(entry => !entry.file || entry.file.size > 20 * 1024 * 1024))
    return toast("Mỗi ảnh phải có dữ liệu và không vượt quá 20 MB.", true);
  if (!metadata.study_date)
    return toast("Chọn ngày khảo sát trước khi chạy.", true);

  const identity = state.user?.id,
    operation = Symbol();
  setBusy(true);
  state.operation = operation;
  state.controller = new AbortController();
  const signal = state.controller.signal,
    active = () => state.user?.id === identity && !signal.aborted && (metadata.isCurrent?.() ?? true);
  const cancel = $("[data-action=cancel-upload]");
  if (cancel) cancel.disabled = true;
  const indicator = setTimeout(() => {
    if (cancel) cancel.disabled = false;
  }, 1000);
  const timeout = setTimeout(() => state.controller?.abort("timeout"), 30 * 60 * 1000);
  const stage = (s, text) => {
    const el = $("#stage-" + s);
    if (el) el.textContent = text;
  };
  const check = () => {
    if (!active())
      throw new DOMException("Đã đổi phiên hoặc dừng chờ", "AbortError");
    if (pending?.lease && !pending.lease.editable)
      throw new DOMException("Quyền chỉnh sửa ca đã hết hạn", "AbortError");
  };
  const leaseHeaders = () => {
    const leaseToken = pending?.lease?.leaseToken?.();
    const pageInstanceId = pending?.lease?.pageInstanceId;
    if (!pending?.lease?.editable || !leaseToken || !pageInstanceId)
      throw new Error("Máy chủ chưa xác nhận quyền chỉnh sửa ca.");
    return {
      "X-Case-Lease-Token": leaseToken,
      "X-Case-Page-Instance-Id": pageInstanceId,
    };
  };
  const uploadIdempotencyKey = (side, entry) => {
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(entry.intakeKey))
      return entry.intakeKey;
    pending.uploadIdempotencyKeys ??= new Map();
    const entryKey = `${side}\0${entry.intakeKey}`;
    if (!pending.uploadIdempotencyKeys.has(entryKey))
      pending.uploadIdempotencyKeys.set(entryKey, crypto.randomUUID());
    return pending.uploadIdempotencyKeys.get(entryKey);
  };
  const ensureCaseLease = async () => {
    if (pending.lease?.editable && pending.lease.leaseToken?.()) return;
    pending.lease?.release();
    pending.lease = null;
    const target = pending;
    const lease = await acquireLease(target.study_id, (message) => {
      target.leaseLost = true;
      if (target === pending && state.user?.id === identity) {
        if (state.operation) state.controller?.abort("lease-lost");
        toast(message, true);
      }
    });
    if (!lease.editable || !lease.leaseToken()) {
      lease.release();
      throw new Error(lease.label || "Máy chủ chưa cấp quyền chỉnh sửa ca.");
    }
    target.lease = lease;
    target.leaseLost = false;
  };
  async function upload(side, entry) {
    check();
    let image = pending.images.find((i) => i.laterality === side && i.intakeKey === entry.intakeKey);
    if (!image) {
      stage(side, `Đang tải ảnh ${entry.index + 1}/${imageEntries[side].length}…`);
      const uploadKey = uploadIdempotencyKey(side, entry);
      const result = await uploadFile(
        entry.file,
        pending.study_id,
        side,
        (p) => {
          const el = $("#progress-" + side);
          if (el) el.value = p;
        },
        signal,
        entry.dicom,
        leaseHeaders(),
        uploadKey,
      );
      check();
      image = {
        ...result,
        laterality: side,
        intakeKey: entry.intakeKey,
        inferenceIdempotencyKey: uploadKey,
        intakeIndex: entry.index,
        viewLabel: `Ảnh ${entry.index + 1}/${imageEntries[side].length}`,
        history: [],
        redo: [],
        seen: false,
        notes: "",
        morphology: "",
      };
      pending.images.push(image);
      tracker.startTask(image.image_id, null);
    }
    return image;
  }
  function open() {
    check();
    state.case = {
      ...pending,
      images: pending.images,
      status: pending.images.every((i) => i.prediction)
        ? "AI_DONE"
        : "IN_REVIEW",
    };
    delete state.case.files;
    pending.lease?.handoff?.();
    pending = null;
    // UAT-03: Re-enable PID field now that the case flow is complete
    const pidInput = document.querySelector("[name=pid]");
    if (pidInput) { pidInput.disabled = false; pidInput.title = ""; }
    location.hash = "#viewer/" + state.case.study_id;
  }
  try {
    const targetPid = (metadata.pid || "").trim();
    if (
      !pending ||
      pending.owner !== identity ||
      pending.files.L !== files.L ||
      pending.files.R !== files.R ||
      pending.active_ovary_side !== activeOvarySide ||
      pending.contralateral_status !== contralateralStatus ||
      (pending.patient_id && targetPid && pending.patient_id !== targetPid) ||
      (pending.requested_pid !== undefined && pending.requested_pid !== targetPid)
    ) {
      pending = null;
      const result = await request("/api/cases", {
        method: "POST",
        body: {
          patient_id:
            targetPid ||
            "BN-" + crypto.randomUUID().slice(0, 8).toUpperCase(),
          active_ovary_side: activeOvarySide,
          contralateral_status: contralateralStatus || "UNKNOWN",
          clinical_notes: state.capabilities?.synthetic_demo_mode === true ? null : metadata.reason,
          study_date: metadata.study_date,
        },
        headers: metadata.idempotency_key
          ? { "Idempotency-Key": metadata.idempotency_key }
          : {},
        signal,
      });
      check();
      pending = {
        ...result,
        owner: identity,
        files: { ...files },
        images: [],
        requested_pid: targetPid,
        active_ovary_side: activeOvarySide,
        contralateral_status: contralateralStatus || "UNKNOWN",
      };
      document.querySelectorAll(".intake-images .dropzone").forEach(zone => { zone.dataset.uploadLocked = "true"; });
      const visitNumber = document.querySelector("[data-visit-no]");
      if (visitNumber) visitNumber.textContent = /^\d{6}$/.test(result.visit_no || "") ? result.visit_no : "Chưa cấp";
      await ensureCaseLease();
      // UAT-03: Lock PID field once a case has been created to prevent stale PID on retry
      const pidInput = document.querySelector("[name=pid]");
      if (pidInput) {
        pidInput.disabled = true;
        pidInput.title = "Mã bệnh nhân đã được ghi nhận cho ca này. Tạo ca mới để thay đổi.";
      }
      try {
        await tracker.startSession(pending.study_id, {
          participant_code: metadata.participant_code,
          participant_role: metadata.participant_role,
          data_origin: metadata.data_origin || "live",
          local_owner_id: identity,
        }, leaseHeaders());
        state.hitl_session = tracker.getSessionId();
      } catch (e) {
        console.warn("HITL session init notice:", e);
      }
    }
    await ensureCaseLease();
    const setStep = (stepNum) => {
      const spans = document.querySelectorAll(".stepper span");
      spans.forEach((s, idx) => {
        s.classList.toggle("current", idx === stepNum - 1);
        s.classList.toggle("done", idx < stepNum - 1);
      });
    };
    setStep(1);
    // Upload each selected still frame before inference so failures preserve the full study.
    for (const side of uploadSides) {
      for (const entry of imageEntries[side]) await upload(side, entry);
    }
    let completedImages = 0;
    for (const side of uploadSides) for (const image of pending.images.filter(item => item.laterality === side)) {
      check();
      if (image.prediction) { completedImages++; continue; }
      setStep(2);
      stage(side, `Kiểm tra chất lượng ảnh ${image.intakeIndex + 1}/${imageEntries[side].length}…`);
      const quality = await request(
        "/api/validate-image?image_id=" + encodeURIComponent(image.image_id),
        { method: "POST", signal, headers: leaseHeaders() },
      );
      image.iqa = quality;
      if (!quality.is_acceptable && !image.iqaOverride) {
        const iqaPct = quality.iqa_score != null ? Math.round(quality.iqa_score * 100) : 0;
        throw Object.assign(
          Error(
            `Ảnh buồng trứng ${side === "L" ? "trái" : "phải"} chưa đạt kiểm chuẩn chất lượng (IQA: ${iqaPct}%): ${quality.message || "Ảnh bị mờ, thiếu tương phản hoặc có bóng cản lớn. Khuyến nghị chỉnh máy siêu âm và chụp lại."}`,
          ),
          { qualityImage: image, qualityReport: quality },
        );
      }
      setStep(3);
      stage(side, `AI đang phân đoạn ảnh ${image.intakeIndex + 1}/${imageEntries[side].length}…`);
      tracker.track(image.image_id, "INFERENCE_START");
      let prediction;
      image.inferenceIdempotencyKey ??= uploadIdempotencyKey(side, imageEntries[side].find(entry => entry.intakeKey === image.intakeKey));
      try {
        prediction = await request(
          "/api/predict/" + encodeURIComponent(image.image_id),
          {
            method: "POST",
            signal,
            headers: { ...leaseHeaders(), "Idempotency-Key": image.inferenceIdempotencyKey },
          },
        );
        tracker.track(image.image_id, "INFERENCE_END");
      } catch (err) {
        tracker.track(image.image_id, "INFERENCE_FAILED", {
          error_type: err.name,
          http_status: err.status,
        });
        throw err;
      }
      check();
      setStep(4);
      image.prediction = prediction;
      image.mask = decode(prediction.rle_mask);
      image.aiMask = image.mask.slice();
      image.source = prediction.original_image_base64;
      image.sourceIsModel = true;
      image.measurements = prediction.measurements;
      image.anonymization = { status: "UNVERIFIED" };
      completedImages++;
      stage(side, `Đã phân đoạn ${completedImages}/${imageCount} ảnh · số đo sẽ cập nhật trong workstation`);
    }
    open();
  } catch (error) {
    const target = $("#intakeError");
    if (target && state.user?.id === identity) {
      target.innerHTML =
        errorBox(
          error.name === "AbortError"
            ? "Đã dừng chờ phản hồi hoặc quá 45 giây. Ảnh đã tải được giữ để thử lại. Tác vụ trên máy chủ có thể vẫn đang chạy."
            : error.message,
          "retry-upload-error",
        ) +
        `<div class="actions" style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">${pending?.images.length >= 1 ? button("Chuyển sang chế độ vẽ tay", "manual-fallback", "quiet") : ""}${error.qualityImage && state.capabilities.iqa_override ? button("Bỏ qua cảnh báo & tiếp tục", "iqa-override", "quiet") : ""}</div>`;
      $("[data-action=retry-upload-error]")?.addEventListener("click", () => {
        if (metadata.onRetry) { metadata.onRetry(); return; }
        const freshPid = (document.querySelector("[name=pid]")?.value || metadata.pid || "").trim();
        startBilateral(files, { ...metadata, pid: freshPid });
      });
      $("[data-action=manual-fallback]")?.addEventListener(
        "click",
        async () => {
          if (state.busy) return;
          setBusy(true);
          const current = pending;
          try {
            for (const image of current.images) {
              if (!image.source) {
                const source = await request(
                  "/api/images/" +
                    encodeURIComponent(image.image_id) +
                    "/viewer-source",
                );
                image.source = source.original_image_base64;
                image.sourceIsModel = true;
              }
              image.mask ??= new Uint8Array(262144);
              image.aiMask ??= image.mask.slice();
            }
            if (state.user?.id !== identity) return;
            state.case = { ...current, status: "IN_REVIEW" };
            delete state.case.files;
            current.lease?.handoff?.();
            pending = null;
            location.hash = "#viewer/" + state.case.study_id;
          } catch (e) {
            toast(e.message, true);
          } finally {
            setBusy(false);
          }
        },
      );
      $("[data-action=iqa-override]")?.addEventListener("click", () =>
        modal(
          "Tiếp tục dù IQA cảnh báo",
          '<p>Cảnh báo được giữ trong workstation. Máy chủ phải ghi nhận lý do và cho phép chạy.</p><label class="field">Lý do<textarea name="reason" required minlength="5"></textarea></label><button class="btn primary" type="submit">Ghi nhận và tiếp tục</button>',
          async (e, d) => {
            const reason = new FormData(e.target).get("reason").trim();
            if (reason.length < 5) return;
            try {
              await request(
                "/api/images/" +
                  encodeURIComponent(error.qualityImage.image_id) +
                  "/iqa-override",
                { method: "POST", body: { reason } },
              );
              error.qualityImage.iqaOverride = true;
              d.close();
              startBilateral(files, metadata);
            } catch (err) {
              toast(err.message, true);
            }
          },
        ),
      );
    }
  } finally {
    clearTimeout(indicator);
    clearTimeout(timeout);
    if (cancel) cancel.disabled = false;
    if (state.operation === operation) {
      setBusy(false);
      state.operation = null;
    }
  }
}
