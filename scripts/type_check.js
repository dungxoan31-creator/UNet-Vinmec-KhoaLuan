#!/usr/bin/env node
/**
 * Static syntax and module validation for frontend and test scripts (QA-02).
 */
import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
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
      console.error(`Syntax/type check failed for: ${fullPath}`);
      console.error(err.stderr ? err.stderr.toString() : err.message);
      process.exit(1);
    }
  }
}

console.log(`PASS: Static type-check verified ${checked} JavaScript modules clean.`);
