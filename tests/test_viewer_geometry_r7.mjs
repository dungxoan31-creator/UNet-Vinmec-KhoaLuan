import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");

test("frontend/css/workspace.css viewer-head has flexible height and wraps on narrow/tablet viewports", () => {
  const css = fs.readFileSync(path.join(rootDir, "frontend/css/workspace.css"), "utf8");

  // Find workstation .viewer-head block (under clinical workstation)
  const blocks = [...css.matchAll(/\.viewer-head\s*\{([^}]+)\}/g)].map((m) => m[1]);
  const workstationHead = blocks.find((b) => b.includes("background: var(--surface)"));
  assert.ok(workstationHead, "workstation .viewer-head rule should exist in workspace.css");

  assert.match(workstationHead, /min-height:\s*48px;?/, ".viewer-head should have min-height: 48px");
  assert.doesNotMatch(workstationHead, /(?<!min-)height:\s*48px;?/, ".viewer-head should not have fixed height: 48px");
  assert.match(workstationHead, /height:\s*auto;?/, ".viewer-head should have height: auto");
  assert.match(workstationHead, /flex:\s*0\s+0\s+auto;?/, ".viewer-head should have flex: 0 0 auto");
  assert.match(workstationHead, /flex-wrap:\s*wrap;?/, ".viewer-head should have flex-wrap: wrap");
});

test("frontend/css/workspace.css has WCAG AA contrast rules for dropzone and admin tables", () => {
  const css = fs.readFileSync(path.join(rootDir, "frontend/css/workspace.css"), "utf8");

  // Dropzone contrast: color #334155
  assert.match(
    css,
    /\.dropzone\s+small\s*,\s*\.dropzone\s+small\.muted[^{]*\{[^}]*color:\s*#334155\s*!important/i,
    ".dropzone small, .dropzone small.muted should specify color: #334155 !important for WCAG AA compliance"
  );

  // Table small contrast: color #334155
  assert.match(
    css,
    /tr\s*>\s*td\s*>\s*small[^{]*\{[^}]*color:\s*#334155\s*!important/i,
    "tr > td > small should specify color: #334155 !important for WCAG AA compliance"
  );
});

test("frontend/app/navigation.js brand link accessible name contains visible label", () => {
  const navCode = fs.readFileSync(path.join(rootDir, "frontend/app/navigation.js"), "utf8");

  assert.match(
    navCode,
    /aria-label="\$\{BRAND_NAME\}\s*—\s*Siêu âm Buồng trứng\s*—\s*Tổng quan"/,
    "brand link aria-label must include visible label 'Siêu âm Buồng trứng · RUO' for WCAG 2.5.3"
  );
});
