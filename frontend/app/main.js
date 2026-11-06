import { applyBrandIdentity } from "./branding.js";
applyBrandIdentity();
import { restoreSession, sessionMonitor } from "./auth.js";
import { bindGlobal, navigate } from "./navigation.js?v=20261103-add-visit";
import { nextCase } from "./workflow.js";
window.addEventListener("ova:next-case", (e) => nextCase(e.detail));
import { state } from "./state.js";
import { saveResearchReview } from "./review.js";
import { request } from "./api.js";
import { updateEnvironmentNotices } from "./environment-notices.js";
document.querySelector(".skip-link").addEventListener("click", (e) => {
  e.preventDefault();
  document.querySelector("#main")?.focus();
});
window.addEventListener("online", () => {
  if (
    state.pendingReview?.userId === state.user?.id &&
    state.pendingReview?.caseId === state.case?.study_id
  )
    saveResearchReview();
});
bindGlobal();
try {
  const health = await request("/api/health");
  if (health?.capabilities) {
    state.capabilities = { ...state.capabilities, ...health.capabilities };
  }
  updateEnvironmentNotices();
} catch {
  // offline or unauthenticated fallback
}
await restoreSession();
updateEnvironmentNotices();
await navigate();
sessionMonitor();
