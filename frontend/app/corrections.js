import { state } from "./state.js";
import { request } from "./api.js";
import { encode } from "./coordinates.js";

import { toast } from "./ui.js";
export async function startCorrection(c, reason) {
  {
    Object.assign(
      c,
      await request(
        "/api/workspace/cases/" +
          encodeURIComponent(c.study_id) +
          "/corrections",
        { method: "POST", body: { version: c.version, reason } },
      ),
    );
  }
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
  state.busy = true;
  const operation = Symbol();
  state.operation = operation;
  try {
    if (c.images.length !== 2 || !c.images.every((i) => i.seen))
      throw Error("Quan sát cả hai ảnh trước khi lưu phiên bản sửa.");
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
          { method: "PUT", body: { version: c.version, images } },
        ),
      );
    }
    if (state.user?.id !== identity) return;
    state.dirty = false;
    localStorage.removeItem(`ova.draft.live.${identity}.${c.study_id}`);
    toast("Đã lưu phiên bản sửa. Bác sĩ phụ trách cần rà soát và ký lại.");
    location.hash = "#case/" + c.study_id;
  } catch (e) {
    toast(e.message, true);
  } finally {
    if (state.operation === operation) {
      state.busy = false;
      state.operation = null;
    }
  }
}
