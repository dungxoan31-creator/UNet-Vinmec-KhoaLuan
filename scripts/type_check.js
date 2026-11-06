#!/usr/bin/env node
/**
 * JavaScript syntax validation. This legacy filename is retained for compatibility;
 * node --check does not perform type analysis or validate runtime imports.
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const root = path.resolve(__dirname, '..');

const targetDirs = [
  path.join(root, 'frontend', 'app'),
  path.join(root, 'frontend', 'js', 'modules'),
];

let checked = 0;
for (const dir of targetDirs) {
  if (!fs.existsSync(dir)) continue;
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.js') || f.endsWith('.mjs'));
  for (const file of files) {
    const fullPath = path.join(dir, file);
    try {
      execFileSync(process.execPath, ['--check', fullPath], { stdio: 'pipe' });
      checked++;
    } catch (err) {
      console.error(`JavaScript syntax check failed for: ${fullPath}`);
      console.error(err.stderr ? err.stderr.toString() : err.message);
      process.exit(1);
    }
  }
}

console.log(`PASS: JavaScript syntax checked ${checked} modules with node --check (no static type analysis).`);
