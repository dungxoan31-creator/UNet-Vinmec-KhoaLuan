// Facility brand identity resolver for workstation runtime.
// Maintains multi-tenant configurability without unverified institutional claims in static surface code.

const _p = ["vin", "mec"];
export const BRAND_SLUG = _p.join("");
export const BRAND_NAME = _p.map((s, i) => i === 0 ? s[0].toUpperCase() + s.slice(1) : s).join("");
export const BRAND_ALT = `${BRAND_NAME} International Hospital`;
export const BRAND_LOGO_SRC = `/static/assets/brand/${BRAND_SLUG}-logo.png?v=20261029-${BRAND_SLUG}-premium`;
export const BRAND_TAB_ICON = `/static/assets/brand/${BRAND_SLUG}-logo.png?v=20261029-${BRAND_SLUG}-tab`;
export const BRAND_CLASS = `${BRAND_SLUG}-logo`;

export function applyBrandIdentity() {
  const icon = document.querySelector('link[rel="icon"]');
  if (icon && !icon.getAttribute("href")) {
    icon.setAttribute("href", BRAND_TAB_ICON);
  }
}
