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
export const autofillState = {
  fields: {
    pid: { value: "", source: "manual", confidence: 1.0, confirmed: false, updatedAt: null },
    studyDate: { value: "", source: "manual", confidence: 1.0, confirmed: false, updatedAt: null },
    patientAge: { value: "", source: "manual", confidence: 1.0, confirmed: false, updatedAt: null },
    laterality: { value: "", source: "manual", confidence: 1.0, confirmed: false, updatedAt: null },
    pixelSpacing: { value: null, source: "manual", confidence: 1.0, confirmed: false, updatedAt: null },
    deviceVendor: { value: "", source: "manual", confidence: 1.0, confirmed: false, updatedAt: null },
  },
  set(field, value, source = "manual", confidence = 1.0) {
    if (!this.fields[field]) {
      this.fields[field] = { value: null, source: "manual", confidence: 1.0, confirmed: false, updatedAt: null };
    }
    this.fields[field].value = value;
    this.fields[field].source = source;
    this.fields[field].confidence = Number(confidence);
    this.fields[field].confirmed = (source === "user" || source === "manual");
    this.fields[field].updatedAt = Date.now();
  },
  confirm(field) {
    if (this.fields[field]) {
      this.fields[field].confirmed = true;
    }
  },
  get(field) {
    return this.fields[field]?.value ?? null;
  },
  provenance(field) {
    return this.fields[field] ?? null;
  },
  reset() {
    for (const key of Object.keys(this.fields)) {
      this.fields[key] = { value: "", source: "manual", confidence: 1.0, confirmed: false, updatedAt: null };
    }
  },
};

export const viewState = {
  activeSide: "L",
  brushSize: 15,
  activeTool: "brush",
  zoom: 1.0,
  panX: 0,
  panY: 0,
  overlayOpacity: 0.45,
  showUncertainty: false,
  showMorphology: true,
  reset() {
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
  },
};

export const caseState = {
  get activeCase() {
    return state.case;
  },
  set activeCase(val) {
    state.case = val;
  },
  get isDirty() {
    return state.dirty;
  },
  set isDirty(val) {
    state.dirty = val;
  },
  get session() {
    return state.hitl_session;
  },
  set session(val) {
    state.hitl_session = val;
  },
};

export const state = {
  user: null,
  token:
    typeof sessionStorage !== "undefined"
      ? sessionStorage.getItem("ova.token")
      : null,
  pendingVerificationEmail: "",
  route: "",
  online: typeof navigator !== "undefined" ? navigator.onLine : true,
  case: null,
  hitl_session: null,
  side: "L",
  dirty: false,
  unattributedMaskDraft: false,
  busy: false,
  pendingReviewTelemetryAck: null,
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
  autofillState,
  viewState,
  caseState,
};
export function setBusy(value) {
  const busy = Boolean(value);
  if (state.busy === busy) return;
  state.busy = busy;
  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    const BusyEvent = window.Event || globalThis.Event;
    if (typeof BusyEvent === "function")
      window.dispatchEvent(new BusyEvent("ova:busy-changed"));
  }
}
export const roles = {
  DOCTOR: "BS",
  BS: "BS",
  SENIOR: "TK",
  TK: "TK",
  ADMIN: "QT",
  QT: "QT",
  TECHNICIAN: "KT",
  KT: "KT",
  KTV: "KT",
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
    "evaluation",
    "profile",
    "preferences",
    "notifications",
    "help",
  ],
  QT: ["dashboard", "admin", "profile", "preferences", "notifications", "help"],
  KT: [
    "dashboard",
    "intake",
    "cases",
    "viewer",
    "case",
    "profile",
    "preferences",
    "notifications",
    "help",
  ],
};
export const can = (route) => permissions[role()]?.includes(route) ?? false;
export function preferences(value) {
  Object.assign(state.preferences, value);
  localStorage.setItem("ova.preferences", JSON.stringify(state.preferences));
}
export function draftKey(id) {
  return `ova.draft.live.${state.user?.id}.${id}`;
}
export function maskDraftKey(studyId, sideOrImageId, userId = state.user?.id) {
  if (userId == null || studyId == null || sideOrImageId == null) return null;
  return `draft_mask_v2:${JSON.stringify([String(userId), String(studyId), String(sideOrImageId)])}`;
}
function removeCaseMaskDrafts(caseRecord) {
  const userId = state.user?.id;
  if (userId == null || !caseRecord?.study_id) return;
  const identifiers = new Set(["L", "R"]);
  for (const image of caseRecord.images || []) if (image?.image_id) identifiers.add(image.image_id);
  for (const identifier of identifiers) localStorage.removeItem(maskDraftKey(caseRecord.study_id, identifier, userId));
}
function hasUnattributedMaskDraft(caseRecord) {
  const identifiers = new Set(["L", "R"]);
  for (const image of caseRecord.images || []) if (image?.image_id) identifiers.add(image.image_id);
  for (const identifier of identifiers) {
    try {
      if (localStorage.getItem(`draft_mask_${caseRecord.study_id}_${identifier}`) !== null) return true;
    } catch {
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("ova:storage-error"));
      return false;
    }
  }
  return false;
}
function validManualCalipers(value, image) {
  if (!Array.isArray(value) || value.length > 2) return false;
  const labels = new Set();
  const width = image.width || image.dimensions?.[0] || 512;
  const height = image.height || image.dimensions?.[1] || 512;
  for (const caliper of value) {
    if (!caliper || !["D1", "D2"].includes(caliper.label) || labels.has(caliper.label) ||
        (caliper.coordinate_space != null && caliper.coordinate_space !== "decoded-source-image") ||
        !Array.isArray(caliper.points) || caliper.points.length !== 2 ||
        caliper.points.some(point => !Array.isArray(point) || point.length !== 2 ||
          point.some((coordinate, axis) => !Number.isFinite(coordinate) || coordinate < 0 || coordinate >= (axis === 0 ? width : height))))
      return false;
    const [a, b] = caliper.points;
    if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 1) return false;
    labels.add(caliper.label);
  }
  return true;
}
export function saveMaskDraft(caseRecord, image) {
  const side = image?.laterality;
  const userId = state.user?.id;
  if (
    userId == null ||
    !caseRecord?.study_id ||
    !image?.image_id ||
    !["L", "R"].includes(side) ||
    !(image.mask instanceof Uint8Array) ||
    image.mask.length !== 512 * 512 ||
    state.draftConflict?.caseId === caseRecord.study_id
  ) return false;
  try {
    const key = maskDraftKey(caseRecord.study_id, image.image_id, userId);
    if (!key) return false;
    localStorage.setItem(
      key,
      JSON.stringify({
        schema_version: 2,
        study_id: caseRecord.study_id,
        image_id: image.image_id,
        side,
        base_version: caseRecord.version ?? null,
        base_review_id: image.review?.review_id ?? null,
        saved_at: Date.now(),
        mask_rle: encode(image.mask),
      }),
    );
    return true;
  } catch {
    window.dispatchEvent(new CustomEvent("ova:storage-error"));
    return false;
  }
}
export function restoreMaskDrafts(caseRecord) {
  state.unattributedMaskDraft = false;
  if (
    state.user?.id == null ||
    !caseRecord?.study_id ||
    !Array.isArray(caseRecord.images)
  ) return [];
  state.unattributedMaskDraft = hasUnattributedMaskDraft(caseRecord);
  if (state.draftConflict?.caseId === caseRecord.study_id) return [];
  const restored = [];
  for (const image of caseRecord.images) {
    const side = image?.laterality;
    if (!image?.image_id || !["L", "R"].includes(side)) continue;
    try {
      const sideImages = caseRecord.images.filter((candidate) => candidate?.laterality === side);
      const imageKey = maskDraftKey(caseRecord.study_id, image.image_id);
      const legacyKey = sideImages.length === 1 ? maskDraftKey(caseRecord.study_id, side) : null;
      const raw = localStorage.getItem(imageKey) ?? (legacyKey ? localStorage.getItem(legacyKey) : null);
      if (!raw) continue;
      const draft = JSON.parse(raw);
      if (
        draft?.schema_version !== 2 ||
        draft.study_id !== caseRecord.study_id ||
        draft.image_id !== image.image_id ||
        draft.side !== side ||
        draft.base_version !== (caseRecord.version ?? null) ||
        draft.base_review_id !== (image.review?.review_id ?? null)
      ) continue;
      image.mask = decode(draft.mask_rle);
      restored.push(sideImages.length === 1 ? side : `${side}:${image.image_id}`);
    } catch {
      continue;
    }
  }
  if (restored.length) state.dirty = true;
  return restored;
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
          notes: i.notes || "",
          morphology: i.morphology || "",
          morphologyDesc: i.morphologyDesc || "",
          orads: i.orads || "",
          manual_calipers: i.manualCalipers || [],
        })),
      }),
    );
  } catch {
    window.dispatchEvent(new CustomEvent("ova:storage-error"));
  }
}
export function restoreDraft(c) {
  state.draftConflict = null;
  if (!state.user?.id || !c || !Array.isArray(c.images)) return false;
  const draft = read(draftKey(c.study_id), null);
  if (!draft) return false;
  const conflict = () => {
    state.draftConflict = { caseId: c.study_id, draft };
    return false;
  };
  if (typeof draft !== "object" || Array.isArray(draft)) return conflict();
  const versionsMatch =
    Object.hasOwn(draft, "base_version") &&
    draft.base_version === (c.version ?? null);
  const reviewsMatch =
    Array.isArray(draft.base_reviews) &&
    draft.base_reviews.length === c.images.length &&
    c.images.every((i) =>
      draft.base_reviews.some(
        (v) => v && typeof v === "object" &&
          v.image_id === i.image_id &&
          v.review_id === (i.review?.review_id ?? null),
      ),
    );
  if (!versionsMatch || !reviewsMatch) {
    return conflict();
  }
  if (!Array.isArray(draft.images) || draft.images.length !== c.images.length)
    return conflict();

  const savedById = new Map();
  for (const saved of draft.images) {
    if (
      !saved ||
      typeof saved !== "object" ||
      typeof saved.image_id !== "string" ||
      savedById.has(saved.image_id) ||
      !c.images.some((image) => image.image_id === saved.image_id) ||
      ["notes", "morphology", "morphologyDesc", "orads"].some(
        (field) => saved[field] != null && typeof saved[field] !== "string",
      ) || (saved.manual_calipers != null && !validManualCalipers(saved.manual_calipers, c.images.find((image) => image.image_id === saved.image_id)))
    )
      return conflict();
    savedById.set(saved.image_id, saved);
  }

  const restored = [];
  try {
    for (const image of c.images) {
      const saved = savedById.get(image.image_id);
      if (!saved) return conflict();
      let mask = image.mask;
      if (saved.mask != null) {
        if (Array.isArray(saved.mask)) {
          if (
            saved.mask.length !== 512 * 512 ||
            saved.mask.some((value) => value !== 0 && value !== 1)
          )
            return conflict();
          mask = Uint8Array.from(saved.mask);
        } else {
          mask = decode(saved.mask);
        }
      }
      restored.push({ image, saved, mask });
    }
  } catch {
    return conflict();
  }

  for (const { image, saved, mask } of restored) {
    image.mask = mask;
    image.notes = saved.notes ?? "";
    image.morphology = saved.morphology ?? "";
    image.morphologyDesc = saved.morphologyDesc || "";
    image.orads = saved.orads || "";
    if (Array.isArray(saved.manual_calipers)) image.manualCalipers = saved.manual_calipers;
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
  removeCaseMaskDrafts(state.case);
  state.draftConflict = null;
  state.dirty = false;
}
export function clearDraft() {
  try {
    if (state.case) {
      localStorage.removeItem(draftKey(state.case.study_id));
      removeCaseMaskDrafts(state.case);
    }
  } catch {
    // The server ACK remains valid even if a stale local draft cannot be removed.
    window.dispatchEvent(new CustomEvent("ova:storage-error"));
  }
  state.dirty = false;
}
