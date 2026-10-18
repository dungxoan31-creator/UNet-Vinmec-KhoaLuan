import { state, roles } from "./state.js";
import { request } from "./api.js";

import { $, field, icon, toast } from "./ui.js";

let expiresAt = 0,
  lockTimer = null;
function clearActive() {
  state.controller?.abort();
  state.cleanup?.();
  state.case = null;
  state.editing = null;
  state.draftConflict = null;
  state.dirty = false;
  state.operation = null;
  state.busy = false;
  state.queue = [];
  state.pendingReview = null;
}
function acceptSession(result) {
  if (!result.access_token || !roles[result.user?.role])
    throw Error("Phản hồi đăng nhập không hợp lệ.");
  clearActive();
  state.token = result.access_token;
  state.user = result.user;

  expiresAt = Date.now() + (result.expires_in || 86400) * 1000;
  state.mustChangePassword = result.password_change_required === true;
  sessionStorage.setItem("ova.token", state.token);
  sessionStorage.setItem("ova.expiry", expiresAt);
  sessionStorage.setItem("ova.lastUsername", state.user.username);
  request("/api/capabilities", { signal: null })
    .then((c) => {
      Object.assign(state.capabilities, c);
    })
    .catch(() => {});
  location.hash = state.mustChangePassword ? "#first" : "#dashboard";
}
export function logout() {
  clearActive();
  state.user = null;
  state.token = null;

  state.mustChangePassword = false;
  sessionStorage.removeItem("ova.token");
  sessionStorage.removeItem("ova.expiry");
  location.hash = "#login";
}
export async function restoreSession() {
  if (!state.token) return;
  try {
    state.user = await request("/api/auth/current-user");
    if (!roles[state.user.role]) throw Error("Vai trò chưa hỗ trợ.");
    expiresAt = Number(sessionStorage.getItem("ova.expiry"));
    try {
      state.capabilities = await request("/api/capabilities");
    } catch {
      state.capabilities = {};
    }
  } catch {
    state.token = null;
    state.user = null;
  }
}
export function renderAuth(mode = "login") {
  clearInterval(lockTimer);
  const titles = {
    login: "Đăng nhập hệ thống",
    register: "Đăng ký tài khoản bác sĩ",
    forgot: "Khôi phục mật khẩu",
    reset: "Đặt lại mật khẩu",
    first: "Đổi mật khẩu lần đầu",
    otp: "Xác thực hai bước",
    expired: "Phiên làm việc đã hết hạn",
  };
  const login = ["login", "expired"].includes(mode),
    register = mode === "register",
    change = ["reset", "first"].includes(mode);
  const resetToken = new URLSearchParams(location.hash.split("?")[1]).get(
    "token",
  );
  const user =
    mode === "expired" ? sessionStorage.getItem("ova.lastUsername") || "" : "";
  return `<div class="auth-layout"><aside class="auth-aside"><div class="brand-mark"><div class="vinmec-logo-card"><img class="vinmec-logo" src="/static/assets/brand/vinmec-logo.png?v=20261018-transparent-logo" alt="Vinmec" width="118" height="72"></div><div class="brand-subtext"><span class="brand-name">VINMEC</span><span class="brand-dept">Chẩn đoán Hình ảnh & Sản Phụ khoa</span></div></div><div class="auth-aside-content"><div class="eyebrow-badge"><span class="pulse-dot"></span><span>HUMAN-IN-THE-LOOP CDSS</span></div><h1>Mỗi đường biên.<br>Một quyết định<br>của người rà soát.</h1><p>Không gian phân đoạn siêu âm hai bên, hiệu chỉnh mask tương tác và lưu vết kiểm toán lâm sàng.</p></div><div class="auth-aside-footer"><div class="auth-badge"><span class="badge-dot"></span><span>Hỗ trợ phân đoạn siêu âm buồng trứng · Vinmec Times City</span></div></div></aside><section class="auth-card"><p class="eyebrow">TRUY CẬP AN TOÀN</p><h2>${titles[mode] || titles.login}</h2><p class="muted">${mode === "expired" ? "Bản nháp được giữ trên thiết bị. Đăng nhập cùng tài khoản để tiếp tục." : mode === "otp" ? "Nhập mã xác thực từ phương thức do đơn vị quản trị cấp." : register ? "Tạo tài khoản bác sĩ mới để tham gia rà soát hình ảnh lâm sàng." : "Sử dụng tài khoản được đơn vị quản trị cấp."}</p><form id="authForm">
        ${login || mode === "forgot" || register ? field("Tên đăng nhập", "username", "text", user, 'required autocomplete="username"') : ""}
        ${register ? field("Họ và tên bác sĩ / chuyên môn", "full_name", "text", "", 'required autocomplete="name"') : ""}
        ${register ? field("Khoa / Phòng ban", "department", "text", "Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa", 'required') : ""}
        ${mode === "otp" ? field("Mã xác thực 6 chữ số", "code", "text", "", 'required inputmode="numeric" pattern="[0-9]{6}" autocomplete="one-time-code"') : ""}
        ${mode === "first" ? field("Mật khẩu hiện tại", "current_password", "password", "", 'required autocomplete="current-password"') : ""}
        ${login || change || register ? `<div class="password-field">${field(change ? "Mật khẩu mới" : "Mật khẩu", "password", "password", "", "required " + (change || register ? 'minlength="6" ' : "") + 'autocomplete="' + (login ? "current-password" : "new-password") + '"')}<button type="button" class="icon-btn" id="showPassword" aria-label="Hiện mật khẩu">${icon("eye")}</button></div>` : ""}
        ${change || register ? field("Nhập lại mật khẩu", "confirm", "password", "", 'required minlength="6" autocomplete="new-password"') : ""}
        ${mode === "reset" && !resetToken ? field("Mã khôi phục được cấp", "token", "text", "", 'required autocomplete="off"') : ""}
        <p id="authError" class="form-error" role="alert"></p><p id="authLock" class="small muted" role="status"></p><button class="btn primary wide" type="submit">${login ? "Đăng nhập" : register ? "Hoàn tất đăng ký" : mode === "otp" ? "Xác thực" : "Tiếp tục"}${icon("arrow")}</button></form>
        ${login ? '<a href="#register" class="text-link" style="display:block;margin-top:12px">Chưa có tài khoản? Đăng ký ngay</a>' : ""}
        ${login ? '<a href="#forgot" class="text-link" style="display:block;margin-top:6px">Quên mật khẩu?</a>' : ""}
        ${!login ? '<a href="#login" class="text-link" style="display:block;margin-top:12px">Quay lại đăng nhập</a>' : ""}
        ${login ? '<div class="auth-quick-login"><p>Đăng nhập nhanh 1-click:</p><div class="auth-quick-btns"><button type="button" class="btn small quiet" data-action="quick-bs">🩺 Bác sĩ</button><button type="button" class="btn small quiet" data-action="quick-admin">🛡️ Quản trị</button></div></div>' : ""}</section></div>`;
}
export function bindAuth(mode) {
  $("#showPassword")?.addEventListener("click", (e) => {
    const p = $("[name=password]");
    p.type = p.type === "password" ? "text" : "password";
    e.currentTarget.setAttribute(
      "aria-label",
      p.type === "password" ? "Hiện mật khẩu" : "Ẩn mật khẩu",
    );
  });
  $("[data-action=quick-bs]")?.addEventListener("click", () => {
    const u = $("[name=username]"),
      p = $("[name=password]");
    if (u) u.value = "doctor";
    if (p) p.value = "doctor-local-test-2026";
    const submitBtn = $("#authForm button[type=submit]");
    if (submitBtn) submitBtn.click();
    else $("#authForm")?.requestSubmit();
  });
  $("[data-action=quick-admin]")?.addEventListener("click", () => {
    const u = $("[name=username]"),
      p = $("[name=password]");
    if (u) u.value = "admin";
    if (p) p.value = "admin-local-test-2026";
    const submitBtn = $("#authForm button[type=submit]");
    if (submitBtn) submitBtn.click();
    else $("#authForm")?.requestSubmit();
  });
  $("#authForm").onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.submitter || $("#authForm button[type=submit]"),
      data = Object.fromEntries(new FormData(e.target));
    $("#authError").textContent = "";
    if (btn) btn.disabled = true;
    let locked = false;
    try {
      if (data.confirm && data.confirm !== data.password)
        throw Error("Hai mật khẩu chưa trùng khớp.");
      if (mode === "register") {
        if (!data.username || data.username.trim().length < 3)
          throw Error("Tên đăng nhập cần ít nhất 3 ký tự.");
        if (!data.password || data.password.length < 6)
          throw Error("Mật khẩu cần ít nhất 6 ký tự.");
        if (data.confirm !== data.password)
          throw Error("Hai mật khẩu chưa trùng khớp.");
        const result = await request("/api/auth/register", {
          method: "POST",
          body: {
            username: data.username.trim(),
            password: data.password,
            full_name: data.full_name?.trim() || data.username.trim(),
            department:
              data.department?.trim() ||
              "Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa",
            role: "DOCTOR",
          },
        });
        toast("Đăng ký tài khoản thành công!");
        acceptSession(result);
        return;
      }
      if (["login", "expired"].includes(mode)) {
        const result = await request("/api/auth/login", {
          method: "POST",
          body: data,
        });
        if (result.otp_required) {
          state.authChallenge = result.challenge_id;
          location.hash = "#otp";
          return;
        }
        acceptSession(result);
      } else if (mode === "otp") {
        if (!state.authChallenge)
          throw Error("Chưa có phiên xác thực OTP. Hãy bắt đầu từ đăng nhập.");
        const result = await request("/api/auth/verify-otp", {
          method: "POST",
          body: { challenge_id: state.authChallenge, code: data.code },
        });
        acceptSession(result);
        state.authChallenge = null;
      } else {
        const endpoint = {
          forgot: "forgot-password",
          reset: "reset-password",
          first: "change-password",
        }[mode];
        const body =
          mode === "forgot"
            ? data
            : {
                ...data,
                new_password: data.password,
                token:
                  data.token ||
                  new URLSearchParams(location.hash.split("?")[1]).get("token"),
              };
        await request("/api/auth/" + endpoint, { method: "POST", body });
        if (mode === "first") state.mustChangePassword = false;
        toast(
          mode === "forgot"
            ? "Nếu tài khoản hợp lệ, máy chủ sẽ gửi hướng dẫn khôi phục."
            : "Yêu cầu đã được máy chủ tiếp nhận.",
        );
        location.hash = mode === "first" ? "#dashboard" : "#login";
      }

    } catch (err) {
      const error = $("#authError");
      if (error)
        error.textContent =
          err.status === 401
            ? "Tên đăng nhập hoặc mật khẩu chưa đúng."
            : err.message;
      if (err.status === 429 && $("#authLock")) {
        locked = true;
        let seconds = Number(err.retryAfter) || 60;
        $("#authLock").textContent =
          `Máy chủ tạm khóa yêu cầu. Thử lại sau ${seconds} giây.`;
        lockTimer = setInterval(() => {
          seconds--;
          const label = $("#authLock");
          if (!label) {
            clearInterval(lockTimer);
            return;
          }
          label.textContent =
            seconds > 0
              ? `Thử lại sau ${seconds} giây.`
              : "Bạn có thể thử đăng nhập lại.";
          if (seconds <= 0) {
            clearInterval(lockTimer);
            if (btn) btn.disabled = false;
          }
        }, 1000);
      }
    } finally {
      if (!locked && btn) btn.disabled = false;
    }
  };
}
export async function renewSession() {
  try {
    const result = await request("/api/auth/refresh", { method: "POST" });
    if (!result.access_token) throw Error("Máy chủ chưa cấp token mới.");
    state.token = result.access_token;
    expiresAt = Date.now() + (result.expires_in || 86400) * 1000;
    sessionStorage.setItem("ova.token", state.token);
    sessionStorage.setItem("ova.expiry", expiresAt);
    $("#sessionWarning")?.remove();
    toast("Đã gia hạn phiên. Bản nháp vẫn được giữ.");
  } catch (e) {
    toast(e.message, true);
  }
}
export function sessionMonitor() {
  setInterval(() => {
    if (!state.user || !expiresAt) return;
    const left = expiresAt - Date.now();
    if (left <= 0) window.dispatchEvent(new CustomEvent("ova:expired"));
    else if (left < 120000 && !$("#sessionWarning") && $("#globalBanners")) {
      const el = document.createElement("div");
      el.id = "sessionWarning";
      el.className = "banner warning";
      el.innerHTML =
        'Phiên sắp hết hạn. Bản nháp được giữ trên thiết bị. <button class="btn small" id="renewSession">Gia hạn phiên</button>';
      $("#globalBanners").append(el);
      $("#renewSession").onclick = renewSession;
    }
  }, 15000);
}
