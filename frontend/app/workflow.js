import { state, role } from "./state.js";
import { getCases } from "./cases.js";
import { toast } from "./ui.js";
export async function nextCase(direction = 1) {
  if (state.busy) return toast("Đang lưu hoặc xử lý. Vui lòng chờ.");
  if (role() === "QT") return;
  try {
    let ids = state.queue;
    if (!ids?.length) {
      const rows = await getCases();
      ids = rows
        .filter((c) =>
          role() === "TK"
            ? c.status === "SIGNED_PRELIM"
            : !["LOCKED", "APPROVED", "SIGNED_PRELIM"].includes(c.status),
        )
        .map((c) => c.study_id);
    }
    if (!ids.length) return toast("Không có ca tiếp theo trong hàng chờ.");
    const current = ids.indexOf(state.case?.study_id),
      index = current < 0 ? 0 : current + direction;
    if (index < 0 || index >= ids.length)
      return toast(
        direction > 0 ? "Đã đến cuối hàng chờ." : "Đã đến đầu hàng chờ.",
      );
    location.hash =
      "#" + (role() === "TK" ? "approval" : "viewer") + "/" + ids[index];
  } catch (e) {
    toast(e.message, true);
  }
}
