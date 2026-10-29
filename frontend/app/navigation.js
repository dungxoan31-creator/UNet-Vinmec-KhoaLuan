import { state, role, can, preferences } from "./state.js";
import { t } from "./i18n.js";
import { $, $$, esc, icon, button, modal, toast } from "./ui.js";
import { renderAuth, bindAuth, logout } from "./auth.js";
import {
  renderDashboard,
  renderCases,
  renderCaseDetail,
  getCasesPage,
} from "./cases.js";
import { renderIntake } from "./intake.js?v=20261025-autofill-v5";
import { renderViewer } from "./viewer.js";
import { renderApproval } from "./approval.js";
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
  evaluation: "chart",
  admin: "settings",
  notifications: "bell",
  help: "help",
  preferences: "settings",
  profile: "users",
};
const authRoutes = ["login", "register", "verify-email", "forgot", "reset", "first", "expired"];
let generation = 0;
let noticeLayoutBound = false;
function syncNoticeStackHeight() {
  const notices = [
    document.querySelector(".ruo-safety-banner"),
    document.querySelector("#environmentUnknownBanner"),
    document.querySelector("#syntheticDemoBanner"),
  ].filter(Boolean);
  const height = notices.reduce((total, notice) => {
    if (notice.hidden || getComputedStyle(notice).display === "none") return total;
    return total + notice.getBoundingClientRect().height;
  }, 0);
  document.documentElement.style.setProperty(
    "--notice-stack-height",
    `${Math.ceil(height)}px`,
  );
}
function bindNoticeStackLayout() {
  if (noticeLayoutBound) return;
  noticeLayoutBound = true;
  const notices = [
    document.querySelector(".ruo-safety-banner"),
    document.querySelector("#environmentUnknownBanner"),
    document.querySelector("#syntheticDemoBanner"),
  ].filter(Boolean);
  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(syncNoticeStackHeight);
    notices.forEach((notice) => resizeObserver.observe(notice));
  }
  const mutationObserver = new MutationObserver(syncNoticeStackHeight);
  notices.forEach((notice) =>
    mutationObserver.observe(notice, {
      attributes: true,
      childList: true,
      characterData: true,
      subtree: true,
      attributeFilter: ["class", "hidden", "style"],
    }),
  );
  window.addEventListener("resize", syncNoticeStackHeight, { passive: true });
  syncNoticeStackHeight();
}
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
  document.body.classList.remove("nav-open");
  const navLinks = Object.entries(routes)
    .filter(
      ([key]) =>
        can(key) &&
        !["preferences", "profile"].includes(key) &&
        !(role() === "BS" && key === "evaluation"),
    )
    .map(
      ([key, ico]) =>
        `<a href="#${key}" title="${esc(t(key, language))}" class="${route === key ? "active" : ""}"${route === key ? ' aria-current="page"' : ""}>${icon(ico)}<span>${esc(t(key, language))}</span></a>`,
    )
    .join("");
  const roleLabel = {
    BS: "Bác sĩ",
    TK: "Chuyên gia rà soát",
    QT: "Quản trị",
  }[role()];
  $("#app").innerHTML = `
    <header class="topbar">
      <button class="icon-btn" id="collapseNav" type="button" aria-label="Thu gọn điều hướng" aria-expanded="true" aria-controls="primaryNav" title="Điều hướng">${icon("menu")}</button>
      <a class="brand" href="#dashboard" aria-label="VINMEC — Tổng quan">
        <img class="vinmec-logo" src="/static/assets/brand/vinmec-logo.png?v=20261029-vinmec-premium" alt="Vinmec International Hospital" width="1616" height="973" decoding="async">
        <span class="brand-product">Siêu âm<small>Buồng trứng · RUO</small></span>
      </a>
      <button class="btn top-search" id="quickSearch" type="button">${icon("search")}Tìm PID hoặc mã ca <kbd>Ctrl K</kbd></button>
      <span class="spacer"></span>
      ${role() !== "QT" ? `<a class="btn quiet next-label" href="#${role() === "TK" ? "approval" : "cases"}">Ca tiếp theo</a>` : ""}
      <button class="icon-btn" id="themeToggle" type="button" aria-label="Chuyển giao diện sáng tối">${icon("sun")}</button>
      <a class="icon-btn" href="#notifications" aria-label="Thông báo">${icon("bell")}</a>
      <button class="btn quiet account-menu" id="accountMenu" type="button" aria-label="Mở tài khoản của ${esc(state.user.full_name || state.user.username)}" aria-haspopup="dialog"><span class="avatar" aria-hidden="true">${esc((state.user.full_name || state.user.username).slice(0, 1))}</span><span class="account-name">${esc(state.user.full_name || state.user.username)}</span></button>
    </header>
    <button class="nav-scrim" id="navScrim" type="button" aria-label="Đóng điều hướng" hidden></button>
    <nav class="sidebar" id="primaryNav" aria-label="Điều hướng chính">
      <p class="nav-label">Công việc</p>
      ${navLinks}
      <div class="nav-bottom">
        <a href="#preferences" aria-label="${esc(t("preferences", language))}" title="${esc(t("preferences", language))}">${icon("settings")}<span>${esc(t("preferences", language))}</span></a>
        <p class="nav-label">${roleLabel}</p>
      </div>
    </nav>
    <main class="main" id="main" tabindex="-1"><div id="globalBanners"></div><div id="page"></div></main>`;
  const navToggle = $("#collapseNav");
  const navScrim = $("#navScrim");
  const primaryNav = $("#primaryNav");
  const mobileNav = window.matchMedia("(max-width: 800px)");
  const setMobileNavOpen = (open, restoreFocus = true) => {
    document.body.classList.toggle("nav-open", open);
    navToggle.setAttribute("aria-expanded", String(open));
    navToggle.setAttribute("aria-label", open ? "Đóng điều hướng" : "Mở điều hướng");
    navScrim.hidden = !open;
    if (open) primaryNav.querySelector("a")?.focus();
    else if (restoreFocus) navToggle.focus();
  };
  const updateNavToggle = () => {
    if (mobileNav.matches) {
      navToggle.setAttribute("aria-expanded", "false");
      navToggle.setAttribute("aria-label", "Mở điều hướng");
    } else {
      const expanded = !document.body.classList.contains("collapsed");
      navToggle.setAttribute("aria-expanded", String(expanded));
      navToggle.setAttribute("aria-label", expanded ? "Thu gọn điều hướng" : "Mở rộng điều hướng");
      navScrim.hidden = true;
    }
  };
  navToggle.onclick = () => {
    if (mobileNav.matches) {
      setMobileNavOpen(!document.body.classList.contains("nav-open"), true);
      return;
    }
    const collapsed = document.body.classList.toggle("collapsed");
    navToggle.setAttribute("aria-expanded", String(!collapsed));
    navToggle.setAttribute("aria-label", collapsed ? "Mở rộng điều hướng" : "Thu gọn điều hướng");
  };
  navScrim.onclick = () => setMobileNavOpen(false);
  primaryNav.addEventListener("click", (event) => {
    if (mobileNav.matches && event.target.closest("a")) setMobileNavOpen(false, false);
  });
  primaryNav.addEventListener("keydown", (event) => {
    if (
      !mobileNav.matches ||
      !document.body.classList.contains("nav-open") ||
      event.key !== "Tab"
    ) return;
    const focusable = [...primaryNav.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')]
      .filter((element) => element.getClientRects().length > 0);
    if (!focusable.length) {
      event.preventDefault();
      navToggle.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  mobileNav.addEventListener("change", () => {
    document.body.classList.remove("nav-open");
    navScrim.hidden = true;
    updateNavToggle();
  });
  updateNavToggle();
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
    '<input id="quickQuery" type="search" class="wide" placeholder="Mã ca, PID giả danh hoặc PID nguồn đầy đủ" aria-label="Từ khóa"><div id="quickResults" style="margin-top:16px"></div>',
  );
  const query = $("#quickQuery");
  if (!query) return;
  let timer;
  let sequence = 0;
  let controller;
  query.oninput = () => {
    const requestId = ++sequence;
    const search = query.value.trim();
    clearTimeout(timer);
    controller?.abort();
    if (!search) {
      $("#quickResults").innerHTML = "";
      return;
    }
    $("#quickResults").textContent = "Đang tìm…";
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const { items: rows } = await getCasesPage(
          { search },
          { signal: controller.signal, limit: 8 },
        );
        if (requestId !== sequence) return;
        $("#quickResults").innerHTML = rows
          .map(
            (c) =>
              `<a class="list-row" href="#case/${c.study_id}">${esc(c.study_code)} · ${esc(c.patient_id)}</a>`,
          )
          .join("") || "<p>Không có kết quả.</p>";
        $$("#quickResults a").forEach(
          (a) => (a.onclick = () => $("#modal").close()),
        );
      } catch (error) {
        if (requestId !== sequence || error.name === "AbortError") return;
        $("#quickResults").textContent = error.message;
      }
    }, 200);
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
  if (!location.hash && typeof location !== "undefined" && location.pathname.endsWith("/admin")) {
    route = "admin";
  }
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
  bindNoticeStackLayout();
  window.addEventListener("hashchange", navigate);
  window.addEventListener("ova:rerender", navigate);
  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !document.body.classList.contains("nav-open")) return;
    document.body.classList.remove("nav-open");
    const navToggle = $("#collapseNav");
    const navScrim = $("#navScrim");
    if (navScrim) navScrim.hidden = true;
    navToggle?.setAttribute("aria-expanded", "false");
    navToggle?.setAttribute("aria-label", "Mở điều hướng");
    navToggle?.focus();
  });
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
  window.addEventListener("ova:hitl-storage-error", () =>
    toast(
      "Không lưu được dự phòng nhật ký HITL trên tab này. Nếu đồng bộ mạng thất bại, nhật ký chưa gửi có thể mất khi đóng trang.",
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
