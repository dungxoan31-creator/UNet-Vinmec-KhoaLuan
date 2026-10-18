import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const reportPreviewFile = path.resolve(__dirname, '../frontend/app/report-preview.js');

const content = fs.readFileSync(reportPreviewFile, 'utf8');

// FE-02: report-preview.js must render saved O-RADS and morphology description
assert(
  content.includes('orads_score') || content.includes('Phân loại O-RADS'),
  "FE-02 VULNERABILITY: report-preview.js does not render saved O-RADS classification!"
);
assert(
  content.includes('morphology_description'),
  "FE-02 VULNERABILITY: report-preview.js does not render saved morphology description!"
);

console.log('PASS: FE-02 report-preview includes orads and morphology description');
