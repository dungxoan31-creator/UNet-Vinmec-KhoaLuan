const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright-core');

exports.startIsolatedBrowser = async function () {
  const root = path.resolve(__dirname, '../..');
  const runtime = fs.mkdtempSync(path.join(os.tmpdir(), 'ova-safety-e2e-'));
  const listener = net.createServer();
  await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const password = 'synthetic-safety-doctor-2026';
  const python = process.env.PYTHON || path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
  const child = spawn(python, ['tests/serve_isolated_app.py'], { cwd: root,
    env: { ...process.env, APP_DATA_DIR: runtime, APP_DB_PATH: path.join(runtime, 'safety.sqlite3'),
      APP_JWT_SECRET: 'synthetic-safety-jwt-secret-2026-10-25',
      APP_PATIENT_PID_HMAC_SECRET: 'synthetic-safety-hmac-secret-2026-10-25',
      APP_DOCTOR_PASSWORD: password, APP_ADMIN_PASSWORD: 'synthetic-safety-admin-2026',
      APP_FEATURES: 'autofill,fast_review,cdss_background,uncertainty_overlay',
      HOST: '127.0.0.1', PORT: String(port) }, stdio: ['ignore', 'pipe', 'pipe'] });
  // Startup diagnostics intentionally omit environment/credentials and database contents.
  let output = '';
  child.stdout.on('data', data => { output = (output + data).slice(-2000); });
  child.stderr.on('data', data => { output = (output + data).slice(-2000); });
  const base = `http://127.0.0.1:${port}`;
  let browser;
  try {
    let ready = false;
    for (let i = 0; i < 360; i++) {
      if (child.exitCode !== null) throw Error('Isolated server exited: ' + output);
      try { if ((await fetch(base + '/api/health/live')).ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    if (!ready) throw Error('Isolated server did not become ready');
    browser = await chromium.launch({ headless: true,
      executablePath: process.env.CHROME_PATH || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined) });
    return { browser, base, password, close: async () => { await browser.close(); child.kill(); } };
  } catch (error) { await browser?.close(); child.kill(); throw error; }
};
