import { state, role } from "./state.js";
import { $, modal, button } from "./ui.js";
export function showOnboardingPrompt() {
  const key = "ova.onboarding." + state.user?.id;
  if (localStorage.getItem(key) || !$("#globalBanners")) return;
  const prompt = document.createElement("div");
  prompt.className = "banner info";
  prompt.id = "onboardingPrompt";
  prompt.innerHTML = `<div><strong>Lần đầu sử dụng?</strong><p>Hướng dẫn nhanh theo vai trò của bạn, khoảng một phút.</p><div class="actions">${button("Bắt đầu hướng dẫn", "start-tour")}${button("Để sau", "later-tour", "quiet")}</div></div>`;
  $("#globalBanners").append(prompt);
  prompt.querySelector("[data-action=start-tour]").onclick = () => {
    prompt.remove();
    startTour();
  };
  prompt.querySelector("[data-action=later-tour]").onclick = () => {
    sessionStorage.setItem(key, "later");
    prompt.remove();
  };
  if (sessionStorage.getItem(key) === "later") prompt.remove();
}
export function startTour() {
  const r = role();
  const steps =
    r === "BS"
      ? [
          [
            "Chuẩn bị cặp ảnh",
            "Mỗi ca cần ảnh Trái và Phải. Hệ thống tự kiểm tra, tải và phân đoạn sau khi đủ hai ảnh hợp lệ.",
          ],
          [
            "Quan sát ảnh trước",
            "Đường viền là mặc định. Giữ Space để xem ảnh gốc; chuyển bên bằng mũi tên trái/phải.",
          ],
          [
            "Hiệu chỉnh có kiểm soát",
            "B vẽ, E tẩy, L tạo đa giác. Ctrl+Z hoàn tác. Mask rỗng không phải kết luận chẩn đoán.",
          ],
          [
            "Hiệu chuẩn và ký",
            "Thiếu spacing chỉ dùng pixel. Xem cả hai ảnh rồi Ctrl+Enter để mở tóm tắt ký sơ bộ.",
          ],
        ]
      : r === "TK"
        ? [
            [
              "Hàng chờ trong khoa",
              "Mở các ca đã ký sơ bộ; ưu tiên ca chờ lâu.",
            ],
            [
              "Rà soát độc lập",
              "Đối chiếu ảnh gốc, mask AI và bản rà soát của bác sĩ. Không tự duyệt ca mình đã ký.",
            ],
            [
              "Duyệt hoặc yêu cầu sửa",
              "Từ chối cần lý do. Ca đã duyệt có thể khóa; sửa sau khóa tạo bản bổ sung.",
            ],
          ]
        : [
            [
              "Quản trị truy cập",
              "Quản lý tài khoản, vai trò và khoa. QT chỉ làm việc với metadata, không đọc ảnh lâm sàng.",
            ],
            [
              "Theo dõi mô hình",
              "Đọc checkpoint và SHA-256 từ registry. Mô hình mới phải qua quy trình triển khai.",
            ],
            [
              "Truy vết và vận hành",
              "Audit Trail chỉ ghi thêm. Kiểm tra sức khỏe hệ thống và bản sao lưu metadata.",
            ],
          ];
  let index = 0;
  const draw = () => {
    const [title, text] = steps[index];
    const d = modal(
      "Hướng dẫn nhanh",
      `<p class="eyebrow">BƯỚC ${index + 1} / ${steps.length}</p><h3>${title}</h3><p>${text}</p><div class="actions">${index ? button("Trước", "tour-prev") : ""}${button(index === steps.length - 1 ? "Hoàn tất" : "Tiếp theo", "tour-next", "primary")}</div>`,
    );
    d.querySelector("[data-action=tour-prev]")?.addEventListener(
      "click",
      () => {
        d.close();
        index--;
        draw();
      },
    );
    d.querySelector("[data-action=tour-next]").onclick = () => {
      d.close();
      if (index < steps.length - 1) {
        index++;
        draw();
      } else localStorage.setItem("ova.onboarding." + state.user.id, "done");
    };
  };
  draw();
}
