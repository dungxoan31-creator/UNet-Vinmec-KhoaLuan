import { state } from "./state.js";

export function isVerifiedResearchEnvironment(capabilities = state.capabilities) {
  return Boolean(
    capabilities &&
    typeof capabilities.synthetic_demo_mode === "boolean" &&
    capabilities.synthetic_demo_uploads_restricted === capabilities.synthetic_demo_mode &&
    capabilities.research_use_only === true &&
    capabilities.clinical_production_ready === false &&
    capabilities.clinical_validation_status === "BLOCKED" &&
    capabilities.case_workflow === false &&
    capabilities.research_export === false,
  );
}

export function updateEnvironmentNotices() {
  const banner = document.getElementById("syntheticDemoBanner");
  const mode = state.capabilities?.synthetic_demo_mode;
  const verified = isVerifiedResearchEnvironment(state.capabilities);
  if (banner) banner.hidden = !verified || mode !== true;
  const unknown = document.getElementById("environmentUnknownBanner");
  if (unknown) unknown.hidden = verified;
}
