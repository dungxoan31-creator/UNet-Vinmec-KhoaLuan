import { state, role, can, preferences } from "./state.js";
import { t } from "./i18n.js";
import { $, $$, esc, icon, button, modal, toast } from "./ui.js";
import { renderAuth, bindAuth, logout } from "./auth.js";
import {
  renderDashboard,
  renderCases,
  renderCaseDetail,
  getCases,
} from "./cases.js";
import { renderIntake } from "./intake.js?v=demo-patients-1";
import { renderViewer } from "./viewer.js";
import { renderApproval } from "./approval.js";
import { renderPatients } from "./patients.js";
import { renderEvaluation } from "./evaluation.js";
import { renderAdmin } from "./admin.js";
import { renderNotifications } from "./notifications.js";
import { renderReport } from "./report-preview.js";
import { renderPersonal } from "./personal.js";
import { nextCase } from "./workflow.js";
import { showOnboardingPrompt } from "./onboarding.js";
const routes = {
  dashboard: "grid",
  intake: "upload",
  cases: "list",
  approval: "check",
  patients: "users",
  evaluation: "chart",
  admin: "settings",
  notifications: "bell",
  help: "help",
  preferences: "settings",
  profile: "users",
};
const authRoutes = ["login", "register", "forgot", "reset", "first", "otp", "expired"];
let generation = 0;
export function applyTheme(route) {
  document.documentElement.dataset.theme =
    state.preferences.theme === "system"
      ? route === "viewer"
        ? "dark"
        : "light"
      : state.preferences.theme;
}
function shell(route) {
  const language = state.preferences.language;
  $("#app").innerHTML =
    `<header class="topbar"><button class="icon-btn" id="collapseNav" aria-label="Thu gọn điều hướng">${icon("menu")}</button><a class="brand" href="#dashboard"><img class="vinmec-logo" src="/static/assets/brand/vinmec-logo.png?v=20261018-transparent-logo" alt="Vinmec" width="81" height="50"><span class="brand-product">Siêu âm<small>BUỒNG TRỨNG</small></span></a><button class="btn top-search" id="quickSearch">${icon("search")}Tìm PID hoặc mã ca <kbd>Ctrl K</kbd></button><span class="spacer"></span>${role() !== "QT" ? '<a class="btn quiet next-label" href="#' + (role() === "TK" ? "approval" : "cases") + '">Ca tiếp theo</a>' : ""}<button class="icon-btn" id="themeToggle" aria-label="Chuyển giao diện sáng tối">${icon("sun")}</button><a class="icon-btn" href="#notifications" aria-label="Thông báo">${icon("bell")}</a><button class="btn quiet" id="accountMenu"><span class="avatar">${esc((state.user.full_name || state.user.username).slice(0, 1))}</span><span class="account-name">${esc(state.user.full_name || state.user.username)}</span></button></header><nav class="sidebar" aria-label="Điều hướng chính"><p class="nav-label">CÔNG VIỆC</p>${Object.entries(
      routes,
    )
      .filter(
        ([key]) =>
          can(key) &&
          !["preferences", "profile"].includes(key) &&
          !(role() === "BS" && key === "evaluation"),
      )
      .map(
        ([key, ico]) =>
          `<a href="#${key}" title="${esc(t(key, language))}" class="${route === key ? "active" : ""}">${icon(ico)}<span>${esc(t(key, language))}</span></a>`,
      )
      .join(
        "",
      )}<div class="nav-bottom"><a href="#preferences">${icon("settings")}<span>Tùy chọn</span></a><p class="nav-label">${{ BS: "BÁC SĨ", TK: "CHUYÊN GIA DUYỆT", QT: "QUẢN TRỊ" }[role()]}</p></div></nav><main class="main" id="main" tabindex="-1"><div id="globalBanners"></div><div id="page"></div></main>`;
  $("#collapseNav").onclick = () => document.body.classList.toggle("collapsed");
  $("#themeToggle").onclick = () => {
    preferences({
      theme:
        document.documentElement.dataset.theme === "dark" ? "light" : "dark",
    });
    applyTheme(route);
  };
  $("#quickSearch").onclick = quickSearch;
  $(".next-label")?.addEventListener("click", (e) => {
    e.preventDefault();
    nextCase();
  });
  $("#accountMenu").onclick = () => {
    const d = modal(
      "Tài khoản",
      `<p>${esc(state.user.username)} · ${role()}</p><div class="actions"><a class="btn" href="#profile" id="profileLink">Hồ sơ cá nhân</a>${button("Đăng xuất", "logout")}</div>`,
    );
    $("#profileLink").onclick = () => d.close();
    $("[data-action=logout]").onclick = () => {
      d.close();
      logout();
    };
  };
}
export async function quickSearch() {
  if (role() === "QT")
    return toast("Tìm kiếm PID không dành cho vai trò quản trị.");
  modal(
    "Tìm nhanh",
    '<input id="quickQuery" type="search" class="wide" placeholder="PID hoặc mã ca" aria-label="Từ khóa"><div id="quickResults" style="margin-top:16px"></div>',
  );
  let rows = [];
  try {
    rows = await getCases();
  } catch (e) {
    $("#quickResults").textContent = e.message;
  }
  const query = $("#quickQuery");
  if (!query) return;
  query.oninput = () => {
    $("#quickResults").innerHTML =
      rows
        .filter((c) =>
          (c.study_code + " " + c.patient_id)
            .toLowerCase()
            .includes(query.value.toLowerCase()),
        )
        .slice(0, 8)
        .map(
          (c) =>
            `<a class="list-row" href="#case/${c.study_id}">${esc(c.study_code)} · ${esc(c.patient_id)}</a>`,
        )
        .join("") || "<p>Không có kết quả.</p>";
    $$("#quickResults a").forEach(
      (a) => (a.onclick = () => $("#modal").close()),
    );
  };
  query.focus();
}
export async function navigate() {
  if (
    state.busy &&
    state.user &&
    state.case &&
    state.route === "viewer" &&
    !authRoutes.includes(location.hash.slice(1).split("/")[0])
  ) {
    history.replaceState(null, "", "#viewer/" + state.case.study_id);
    toast("Đang lưu rà soát. Vui lòng chờ.");
    return;
  }
  const gen = ++generation;
  state.routeController?.abort();
  state.routeController = new AbortController();
  state.cleanup?.();
  state.cleanup = () => {};
  let [route = "dashboard", id] = location.hash
    .slice(1)
    .split("?")[0]
    .split("/");
  route = route || "dashboard";
  if (route === "evaluation" && role() === "BS") {
    location.hash = "#dashboard";
    return;
  }
  if (
    state.mustChangePassword &&
    !["first", "login", "expired"].includes(route)
  ) {
    location.hash = "#first";
    return;
  }
  state.route = route;
  window.scrollTo(0, 0);
  document.body.classList.toggle("viewer-mode", route === "viewer");
  applyTheme(route);
  if (authRoutes.includes(route) || !state.user) {
    $("#app").innerHTML = renderAuth(
      authRoutes.includes(route) ? route : "login",
    );
    bindAuth(authRoutes.includes(route) ? route : "login");
    return;
  }
  shell(route);
  const root = $("#page");
  if (
    ["403", "404", "maintenance"].includes(route) ||
    (!can(route) && !["case", "viewer", "report"].includes(route))
  ) {
    const code =
      route === "maintenance"
        ? "503"
        : route === "403" || Object.hasOwn(routes, route)
          ? "403"
          : "404";
    root.innerHTML = `<div class="error-page"><div class="error-code">${code}</div><h1>${code === "403" ? "Không có quyền truy cập" : code === "503" ? "Hệ thống đang bảo trì" : "Không tìm thấy trang"}</h1><p class="muted">${code === "403" ? "Vai trò hiện tại không được sử dụng chức năng này." : "Bạn có thể quay lại tổng quan hoặc thử tải lại."}</p><a class="btn primary" href="#dashboard">Về tổng quan</a></div>`;
    return;
  }
  if (!can(route)) {
    location.hash = "#403";
    return;
  }
  try {
    let cleanup;
    if (route === "dashboard") cleanup = await renderDashboard(root);
    else if (route === "cases") cleanup = await renderCases(root);
    else if (route === "intake") cleanup = renderIntake(root);
    else if (route === "viewer") cleanup = await renderViewer(root, id);
    else if (route === "case") cleanup = await renderCaseDetail(root, id);
    else if (route === "report") cleanup = await renderReport(root, id);
    else if (route === "approval") cleanup = await renderApproval(root, id);
    else if (route === "patients")
      cleanup = await renderPatients(root, id ? decodeURIComponent(id) : null);
    else if (route === "evaluation") cleanup = await renderEvaluation(root);
    else if (route === "admin") cleanup = await renderAdmin(root, id);
    else if (route === "notifications")
      cleanup = await renderNotifications(root);
    else cleanup = renderPersonal(root, route);
    if (gen === generation && route === "dashboard") showOnboardingPrompt();
    if (gen === generation)
      state.cleanup = typeof cleanup === "function" ? cleanup : () => {};
    else cleanup?.();
  } catch (e) {
    root.innerHTML = `<div class="banner danger" role="alert">${esc(e.message)}</div>`;
  }
}
export function bindGlobal() {
  window.addEventListener("hashchange", navigate);
  window.addEventListener("ova:rerender", navigate);
  window.addEventListener("ova:expired", () => {
    if (state.route === "expired" || !state.user) return;
    state.controller?.abort();
    state.routeController?.abort();
    state.cleanup?.();
    state.case = null;
    state.dirty = false;
    state.user = null;
    state.token = null;
    sessionStorage.removeItem("ova.token");
    location.hash = "#expired";
  });
  window.addEventListener("ova:storage-error", () =>
    toast(
      "Không lưu được bản nháp trên thiết bị. Giữ trang mở và thử lưu lại.",
      true,
    ),
  );
  for (const type of ["online", "offline"])
    window.addEventListener(type, () => {
      state.online = navigator.onLine;
      $("#connectionText").textContent = state.online
        ? "Đã kết nối"
        : "Mất mạng · bản nháp cục bộ";
    });
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (state.user) quickSearch();
    }
  });
  window.addEventListener("beforeunload", (e) => {
    if (state.dirty || state.busy) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}
