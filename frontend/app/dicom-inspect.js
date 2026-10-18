import { state } from "./state.js";
import { request } from "./api.js";
import { modal, esc, toast } from "./ui.js";

export async function inspectDicom(file, side) {
  if (state.capabilities.dicom_inspection !== true)
    return {
      file,
      frame: null,
      label:
        "DICOM: máy chủ hiện chỉ nhận ảnh siêu âm một khung. Chưa có kiểm tra ẩn danh.",
    };
  const body = new FormData();
  body.append("file", file);
  body.append("laterality", side);
  const result = await request("/api/uploads/inspect", {
    method: "POST",
    body,
  });
  if (
    !result.upload_id ||
    !Number.isInteger(result.number_of_frames) ||
    result.number_of_frames < 1
  )
    throw Error("Thông tin DICOM chưa đúng contract.");
  let frame = 0;
  if (result.number_of_frames > 1) {
    const response = await request(
      "/api/uploads/" + encodeURIComponent(result.upload_id) + "/frames",
    );
    if (
      !Array.isArray(response.frames) ||
      response.frames.length !== result.number_of_frames
    )
      throw Error("Máy chủ chưa cung cấp đủ ảnh xem trước các khung.");
    frame = await new Promise((resolve) => {
      const d = modal(
        "Chọn khung DICOM · " + (side === "L" ? "Trái" : "Phải"),
        '<p>Mỗi bên dùng một ảnh tĩnh. Kiểm tra đúng mặt phẳng trước khi chọn.</p><div class="frame-grid">' +
          response.frames
            .map(
              (f, n) =>
                `<label class="frame-option"><input type="radio" name="frame" value="${n}" ${n === 0 ? "checked" : ""}><img src="${esc(f.preview_base64)}" alt="Khung ${n + 1}"><span>Khung ${n + 1}</span></label>`,
            )
            .join("") +
          '</div><button class="btn primary" type="submit">Sử dụng khung đã chọn</button>',
        (e, dialog) => {
          dialog.returnValue = String(new FormData(e.target).get("frame"));
          dialog.close();
        },
      );
      d.addEventListener(
        "close",
        () =>
          resolve(
            d.returnValue === "cancel" || d.returnValue === ""
              ? null
              : Number(d.returnValue),
          ),
        { once: true },
      );
    });
    if (frame === null) throw Error("Chưa chọn khung DICOM.");
  }
  if (result.anonymization?.status !== "VERIFIED")
    toast(
      "DICOM chưa được máy chủ xác minh ẩn danh. Không dùng dữ liệu định danh thật.",
      true,
    );
  return {
    file,
    frame,
    upload_id: result.upload_id,
    anonymous_pid: result.anonymous_pid,
    metadata: result,
    label: `DICOM · khung ${frame + 1}/${result.number_of_frames} · ${result.pixel_spacing ? "Có spacing do máy chủ cung cấp" : "Thiếu PixelSpacing – chỉ dùng px"}`,
  };
}
