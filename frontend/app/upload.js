import { state } from "./state.js";
import { request, uploadFile } from "./api.js";
import { decode } from "./coordinates.js";
import { $, errorBox, button, toast, modal } from "./ui.js";
import { tracker } from "./hitl-tracker.js";
let pending = null;

export async function startBilateral(files, metadata) {
  if (state.busy) return;
  if (!files.L || !files.R)
    return toast("Cần đủ ảnh trái và phải trước khi chạy.", true);

  const identity = state.user?.id,
    operation = Symbol();
  state.busy = true;
  state.operation = operation;
  state.controller = new AbortController();
  const signal = state.controller.signal,
    active = () => state.user?.id === identity && !signal.aborted;
  const cancel = $("[data-action=cancel-upload]");
  if (cancel) cancel.disabled = true;
  const indicator = setTimeout(() => {
    if (cancel) cancel.disabled = false;
  }, 1000);
  const timeout = setTimeout(() => state.controller?.abort("timeout"), 45000);
  const stage = (s, text) => {
    const el = $("#stage-" + s);
    if (el) el.textContent = text;
  };
  const check = () => {
    if (!active())
      throw new DOMException("Đã đổi phiên hoặc dừng chờ", "AbortError");
  };
  async function upload(side) {
    check();
    let image = pending.images.find((i) => i.laterality === side);
    if (!image) {
      stage(side, "Đang tải ảnh…");
      const result = await uploadFile(
        files[side],
        pending.study_id,
        side,
        (p) => {
          const el = $("#progress-" + side);
          if (el) el.value = p;
        },
        signal,
        metadata.dicom?.[side],
      );
      check();
      image = {
        ...result,
        laterality: side,
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
          active_ovary_side: "BOTH",
          clinical_notes: metadata.reason,
          study_date: (() => {
            const d = new Date();
            return [
              d.getFullYear(),
              String(d.getMonth() + 1).padStart(2, "0"),
              String(d.getDate()).padStart(2, "0"),
            ].join("-");
          })(),
        },
        signal,
      });
      check();
      pending = { ...result, owner: identity, files: { ...files }, images: [], requested_pid: targetPid };
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
        });
        state.hitl_session = tracker.getSessionId();
      } catch (e) {
        console.warn("HITL session init notice:", e);
      }
    }
    const setStep = (stepNum) => {
      const spans = document.querySelectorAll(".stepper span");
      spans.forEach((s, idx) => {
        s.classList.toggle("current", idx === stepNum - 1);
        s.classList.toggle("done", idx < stepNum - 1);
      });
    };
    setStep(1);
    // Upload both sides before inference so a failed model can still lead to manual review.
    for (const side of ["L", "R"]) await upload(side);
    for (const side of ["L", "R"]) {
      check();
      const image = pending.images.find((i) => i.laterality === side);
      if (image.prediction) continue;
      setStep(2);
      stage(side, "Kiểm tra chất lượng ảnh…");
      const quality = await request(
        "/api/validate-image?image_id=" + encodeURIComponent(image.image_id),
        { method: "POST", signal },
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
      stage(side, "AI đang phân đoạn…");
      tracker.track(image.image_id, "INFERENCE_START");
      let prediction;
      try {
        prediction = await request(
          "/api/predict/" + encodeURIComponent(image.image_id),
          { method: "POST", signal },
        );
        tracker.track(image.image_id, "INFERENCE_END");
      } catch (err) {
        tracker.track(image.image_id, "INFERENCE_FAILED", {
          error: err.message,
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
      stage(side, "Đã phân đoạn · số đo sẽ cập nhật trong workstation");
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
        `<div class="actions" style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">${pending?.images.length === 2 ? button("Chuyển sang chế độ vẽ tay", "manual-fallback", "quiet") : ""}${error.qualityImage && state.capabilities.iqa_override ? button("Bỏ qua cảnh báo & tiếp tục", "iqa-override", "quiet") : ""}</div>`;
      $("[data-action=retry-upload-error]")?.addEventListener("click", () => {
        const freshPid = (document.querySelector("[name=pid]")?.value || metadata.pid || "").trim();
        startBilateral(files, { ...metadata, pid: freshPid });
      });
      $("[data-action=manual-fallback]")?.addEventListener(
        "click",
        async () => {
          if (state.busy) return;
          state.busy = true;
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
            pending = null;
            location.hash = "#viewer/" + state.case.study_id;
          } catch (e) {
            toast(e.message, true);
          } finally {
            state.busy = false;
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
      state.busy = false;
      state.operation = null;
    }
  }
}
