import { clearDraft, state, setBusy } from "./state.js";
import { request } from "./api.js";
import { encode } from "./coordinates.js";

import { toast } from "./ui.js";
export async function startCorrection(c, technicianId, reason) {
  if (!technicianId || !reason?.trim())
    throw Error("Chọn TK và nhập lý do hiệu chỉnh.");
  Object.assign(
    c,
    await request(
      "/api/workspace/cases/" +
        encodeURIComponent(c.study_id) +
        "/corrections",
      { method: "POST", body: { technician_id: technicianId, reason: reason.trim() } },
    ),
  );
  location.hash = "#viewer/" + c.study_id;
}
export async function saveCorrection() {
  const c = state.case,
    identity = state.user?.id;
  if (
    state.busy ||
    c?.correction_by !== identity ||
    state.editing?.caseId !== c.study_id ||
    !state.editing.allowed
  )
    return;
  setBusy(true);
  const operation = Symbol();
  state.operation = operation;
  try {
    if (!c.images?.length || c.images.length > 20 || !c.images.every((i) => i.seen))
      throw Error("Quan sát tất cả ảnh thuộc ca (1–20 ảnh) trước khi lưu phiên bản sửa.");
    const images = c.images.map((i) => ({
      image_id: i.image_id,
      verified_mask_rle: encode(i.mask),
      notes: i.notes,
      morphology: i.morphology,
    }));
    {
      Object.assign(
        c,
        await request(
          "/api/workspace/cases/" +
            encodeURIComponent(c.study_id) +
            "/corrections",
          {
            method: "PUT",
            body: {
              correction_id: c.correction_id,
              base_revision: c.correction_revision,
              lease_token: state.editing.leaseToken,
              page_instance_id: state.editing.pageInstanceId,
              draft_payload: { images },
            },
          },
        ),
      );
    }
    if (state.user?.id !== identity) return;
    state.dirty = false;
    clearDraft();
    toast("Đã lưu phiên bản sửa. Bác sĩ phụ trách cần rà soát và ký lại.");
    location.hash = "#case/" + c.study_id;
  } catch (e) {
    toast(e.message, true);
  } finally {
    if (state.operation === operation) {
      setBusy(false);
      state.operation = null;
    }
  }
}
