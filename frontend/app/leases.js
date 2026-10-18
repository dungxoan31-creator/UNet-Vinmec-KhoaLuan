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

// Tab identity relies solely on sessionStorage, which is scoped per tab and
// survives reload but is NOT shared between tabs. No BroadcastChannel
// collision-detection is needed: a genuine duplicate tab always gets a fresh
// sessionStorage (and thus a new UUID), while a reloaded tab keeps the same
// UUID — exactly the behaviour we want for lease continuity on reload.

const read = (key) => {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
};
// A cross-tab guard supplements a server lease; it cannot protect other devices.
export async function acquireLease(caseId, onLost) {
  const key = "ova.lease." + "live." + caseId,
    existing = read(key);
  if (existing && existing.expires_at > Date.now() && existing.tab_id !== tabId)
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
    const response = await request(
      "/api/workspace/cases/" + encodeURIComponent(caseId) + "/lease",
      { method: "POST", body: { tab_id: tabId } },
    );
    if (!response.granted)
      return {
        editable: false,
        label: "Ca đang được người khác chỉnh. Phiên này chỉ xem.",
        release: () => {},
      };
    serverLease = response;
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
    if (other && other.expires_at > Date.now() && other.tab_id !== tabId) {
      lose();
      return;
    }
    try {
      localStorage.setItem(
        key,
        JSON.stringify({
          tab_id: tabId,
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
      if (other && other.expires_at > Date.now() && other.tab_id !== tabId)
        lose();
    }
  };
  const onPageHide = () => {
    try {
      const cur = read(key);
      if (cur && cur.tab_id === tabId) {
        cur.expires_at = Date.now() + 5000;
        localStorage.setItem(key, JSON.stringify(cur));
      }
    } catch {}
  };
  window.addEventListener("pagehide", onPageHide);

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
            body: { lease_token: serverLease.lease_token, tab_id: tabId },
          },
        );
        if (!next.granted) {
          lose();
          return;
        }
        serverLease = next;
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
    if (read(key)?.tab_id === tabId) localStorage.removeItem(key);
    if (remote && serverLease)
      fetch("/api/workspace/cases/" + encodeURIComponent(caseId) + "/lease", {
        method: "DELETE",
        headers: {
          Authorization: "Bearer " + session.token,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ lease_token: serverLease.lease_token }),
        keepalive: true,
      }).catch(() => {});
  }
  return {
    editable: !stopped,
    label: remote
      ? "Phiên chỉnh sửa được máy chủ giữ."
      : "Chỉ bảo vệ giữa các tab trên thiết bị; máy chủ chưa cung cấp khóa đa người dùng.",
    release,
  };
}
