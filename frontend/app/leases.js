import { state } from "./state.js";
import { request } from "./api.js";
let tabId = (() => {
  try {
    let id = sessionStorage.getItem("ova.tab_id");
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem("ova.tab_id", id);
    }
    return id;
  } catch {
    return crypto.randomUUID();
  }
})();
const pageInstanceId = (() => {
  const key = "ova.page_instance_id";
  const navigation = performance.getEntriesByType?.("navigation")?.[0]?.type;
  try {
    const prior = sessionStorage.getItem(key);
    if (prior && navigation === "reload") return prior;
    const id = crypto.randomUUID();
    sessionStorage.setItem(key, id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
})();
const reloadGraceMs = 10000;

// sessionStorage survives reloads and may also be cloned when a tab is duplicated.
// The page instance id and local lease record distinguish those live documents.

const read = (key) => {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
};
const heldByAnotherPage = (record) =>
  Boolean(
    record &&
      record.expires_at > Date.now() + reloadGraceMs &&
      (record.tab_id !== tabId || record.instance_id !== pageInstanceId),
  );
// A cross-tab guard supplements a server lease; it cannot protect other devices.
export async function acquireLease(caseId, onLost) {
  const key = "ova.lease." + "live." + caseId,
    existing = read(key);
  if (heldByAnotherPage(existing))
    return {
      editable: false,
      label: "Ca đang được chỉnh ở tab khác. Phiên này chỉ xem.",
      release: () => {},
    };
  const session = {
      user: state.user?.id,
      token: state.token,
    },
    remote = state.capabilities.case_leases === true;
  let serverLease = null,
    stopped = false,
    timer;
  const current = () =>
    session.user === state.user?.id && session.token === state.token;
  if (remote) {
    let priorToken = null;
    try {
      priorToken = sessionStorage.getItem("ova.server-lease." + caseId);
    } catch {}
    let response;
    try {
      response = await request(
        "/api/workspace/cases/" + encodeURIComponent(caseId) + "/lease",
        {
          method: "POST",
          body: {
            tab_id: tabId,
            page_instance_id: pageInstanceId,
            ...(priorToken ? { lease_token: priorToken } : {}),
          },
        },
      );
    } catch {
      onLost("Máy chủ chưa xác nhận quyền chỉnh sửa; phiên này chỉ xem.");
      return {
        editable: false,
        label: "Không thể xác nhận quyền chỉnh sửa với máy chủ.",
        release: () => {},
      };
    }
    if (!response.granted)
      return {
        editable: false,
        label: "Ca đang được người khác chỉnh. Phiên này chỉ xem.",
        release: () => {},
      };
    serverLease = response;
    try {
      sessionStorage.setItem("ova.server-lease." + caseId, response.lease_token);
    } catch {}
  }
  function lose() {
    if (stopped) return;
    stopped = true;
    clearInterval(timer);
    onLost(
      "Mất quyền giữ phiên chỉnh sửa. Bản nháp được giữ; chuyển sang chỉ xem.",
    );
  }
  function write() {
    const other = read(key);
    if (heldByAnotherPage(other)) {
      lose();
      return;
    }
    try {
      localStorage.setItem(
        key,
        JSON.stringify({
          tab_id: tabId,
          instance_id: pageInstanceId,
          owner: session.user,
          expires_at: Date.now() + 45000,
        }),
      );
    } catch {
      lose();
    }
  }
  const storage = (e) => {
    if (e.key === key) {
      const other = read(key);
      if (heldByAnotherPage(other)) lose();
    }
  };
  const onPageHide = () => {
    try {
      const cur = read(key);
      if (cur && cur.tab_id === tabId && cur.instance_id === pageInstanceId) {
        cur.expires_at = Date.now() + 5000;
        localStorage.setItem(key, JSON.stringify(cur));
      }
    } catch {}
  };
  const onPageShow = () => {
    const other = read(key);
    if (heldByAnotherPage(other)) lose();
  };
  window.addEventListener("pagehide", onPageHide);
  window.addEventListener("pageshow", onPageShow);

  write();
  window.addEventListener("storage", storage);
  timer = setInterval(async () => {
    if (!current()) {
      lose();
      return;
    }
    if (remote)
      try {
        const next = await request(
          "/api/workspace/cases/" + encodeURIComponent(caseId) + "/lease",
          {
            method: "POST",
            body: {
              lease_token: serverLease.lease_token,
              tab_id: tabId,
              page_instance_id: pageInstanceId,
            },
          },
        );
        if (!next.granted) {
          lose();
          return;
        }
        serverLease = next;
        try {
          sessionStorage.setItem("ova.server-lease." + caseId, next.lease_token);
        } catch {}
      } catch {
        lose();
        return;
      }
    write();
  }, 15000);
  function release() {
    stopped = true;
    clearInterval(timer);
    window.removeEventListener("storage", storage);
    window.removeEventListener("pagehide", onPageHide);
    window.removeEventListener("pageshow", onPageShow);
    const currentLease = read(key);
    if (
      currentLease?.tab_id === tabId &&
      currentLease?.instance_id === pageInstanceId
    )
      localStorage.removeItem(key);
    if (remote && serverLease)
      fetch("/api/workspace/cases/" + encodeURIComponent(caseId) + "/lease", {
        method: "DELETE",
        headers: {
          Authorization: "Bearer " + session.token,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          lease_token: serverLease.lease_token,
          page_instance_id: pageInstanceId,
        }),
        keepalive: true,
      }).catch(() => {});
    if (remote && serverLease)
      try {
        const key = "ova.server-lease." + caseId;
        if (sessionStorage.getItem(key) === serverLease.lease_token)
          sessionStorage.removeItem(key);
      } catch {}
  }
  function handoff() {
    stopped = true;
    clearInterval(timer);
    window.removeEventListener("storage", storage);
    window.removeEventListener("pagehide", onPageHide);
    window.removeEventListener("pageshow", onPageShow);
  }
  return {
    editable: !stopped,
    leaseToken: () => serverLease?.lease_token ?? null,
    pageInstanceId,
    label: "",
    handoff,
    release,
  };
}
