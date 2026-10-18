import { encode, decode } from "./coordinates.js";
const read = (key, fallback) => {
  try {
    return typeof localStorage !== "undefined"
      ? (JSON.parse(localStorage.getItem(key)) ?? fallback)
      : fallback;
  } catch {
    return fallback;
  }
};
export const state = {
  user: null,
  token:
    typeof sessionStorage !== "undefined"
      ? sessionStorage.getItem("ova.token")
      : null,
  route: "",
  online: typeof navigator !== "undefined" ? navigator.onLine : true,
  case: null,
  hitl_session: null,
  side: "L",
  dirty: false,
  busy: false,
  controller: null,
  capabilities: {},
  preferences: {
    theme: "system",
    language: "vi",
    layout: "single",
    ...read("ova.preferences", {}),
  },
  notifications: [],
  cleanup: () => {},
};
export const roles = {
  DOCTOR: "BS",
  BS: "BS",
  SENIOR: "TK",
  TK: "TK",
  ADMIN: "QT",
  QT: "QT",
};
export const role = () => roles[state.user?.role] ?? null;
export const permissions = {
  BS: [
    "dashboard",
    "intake",
    "cases",
    "viewer",
    "case",
    "report",
    "patients",
    "evaluation",
    "profile",
    "preferences",
    "notifications",
    "help",
  ],
  TK: [
    "dashboard",
    "cases",
    "viewer",
    "case",
    "report",
    "approval",
    "patients",
    "evaluation",
    "profile",
    "preferences",
    "notifications",
    "help",
  ],
  QT: ["dashboard", "admin", "profile", "preferences", "notifications", "help"],
};
export const can = (route) => permissions[role()]?.includes(route) ?? false;
export function preferences(value) {
  Object.assign(state.preferences, value);
  localStorage.setItem("ova.preferences", JSON.stringify(state.preferences));
}
export function draftKey(id) {
  return `ova.draft.live.${state.user?.id}.${id}`;
}
export function saveDraft() {
  if (!state.case || state.draftConflict) return;
  state.dirty = true;
  try {
    localStorage.setItem(
      draftKey(state.case.study_id),
      JSON.stringify({
        updated_at: Date.now(),
        base_version: state.case.version ?? null,
        base_reviews: state.case.images.map((i) => ({
          image_id: i.image_id,
          review_id: i.review?.review_id ?? null,
        })),
        images: state.case.images.map((i) => ({
          image_id: i.image_id,
          mask: i.mask ? encode(i.mask) : null,
          notes: i.notes || "",
          morphology: i.morphology || "",
          morphologyDesc: i.morphologyDesc || "",
          orads: i.orads || "",
        })),
      }),
    );
  } catch {
    window.dispatchEvent(new CustomEvent("ova:storage-error"));
  }
}
export function restoreDraft(c) {
  state.draftConflict = null;
  const draft = read(draftKey(c.study_id), null);
  if (!draft) return false;
  const versionsMatch =
    Object.hasOwn(draft, "base_version") &&
    draft.base_version === (c.version ?? null);
  const reviewsMatch =
    Array.isArray(draft.base_reviews) &&
    c.images.every((i) =>
      draft.base_reviews.some(
        (v) =>
          v.image_id === i.image_id &&
          v.review_id === (i.review?.review_id ?? null),
      ),
    );
  if (!versionsMatch || !reviewsMatch) {
    state.draftConflict = { caseId: c.study_id, draft };
    return false;
  }
  for (const i of c.images) {
    const saved = draft.images.find((v) => v.image_id === i.image_id);
    if (saved) {
      i.mask = saved.mask
        ? Array.isArray(saved.mask)
          ? Uint8Array.from(saved.mask)
          : decode(saved.mask)
        : i.mask;
      i.notes = saved.notes;
      i.morphology = saved.morphology;
      i.morphologyDesc = saved.morphologyDesc || "";
      i.orads = saved.orads || "";
    }
  }
  return true;
}
export function keepServerVersion() {
  if (!state.case || state.draftConflict?.caseId !== state.case.study_id)
    return;
  const key = draftKey(state.case.study_id);
  localStorage.setItem(
    key + ".conflict." + Date.now(),
    JSON.stringify(state.draftConflict.draft),
  );
  localStorage.removeItem(key);
  state.draftConflict = null;
  state.dirty = false;
}
export function clearDraft() {
  if (state.case) localStorage.removeItem(draftKey(state.case.study_id));
  state.dirty = false;
}
