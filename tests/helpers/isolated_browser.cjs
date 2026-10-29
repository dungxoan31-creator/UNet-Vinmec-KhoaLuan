const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const { randomBytes } = require('node:crypto');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright-core');

function waitForExit(child, timeoutMs) {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve(true);
  return new Promise(resolve => {
    const onExit = () => {
      clearTimeout(timer);
      resolve(true);
    };
    const timer = setTimeout(() => {
      child.off('exit', onExit);
      resolve(child.exitCode !== null || child.signalCode !== null);
    }, timeoutMs);
    child.once('exit', onExit);
  });
}

async function stopChild(child) {
  if (child.exitCode !== null || child.signalCode !== null) return;
  const exited = waitForExit(child, 3000);
  child.kill();
  if (await exited) return;
  const forceExited = waitForExit(child, 3000);
  child.kill('SIGKILL');
  if (!(await forceExited)) throw new Error('Isolated test server did not stop; runtime data was retained.');
}

function probeListener(port) {
  return new Promise(resolve => {
    const socket = net.createConnection({ host: '127.0.0.1', port });
    let settled = false;
    const finish = state => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(state);
    };
    socket.once('connect', () => finish('open'));
    socket.once('error', error => finish(error.code === 'ECONNREFUSED' ? 'closed' : 'unknown'));
    socket.setTimeout(500, () => finish('unknown'));
  });
}

async function assertListenerStopped(port) {
  const deadline = Date.now() + 3000;
  while (Date.now() < deadline) {
    if (await probeListener(port) === 'closed') return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('Isolated server listener may still be active; runtime data was retained.');
}

function removeRuntime(runtime) {
  fs.rmSync(runtime, {
    recursive: true,
    force: true,
    maxRetries: 10,
    retryDelay: 250,
  });
}

exports.startIsolatedBrowser = async function ({ syntheticFixtureDir } = {}) {
  const root = path.resolve(__dirname, '../..');
  const runtime = fs.mkdtempSync(path.join(os.tmpdir(), 'ova-safety-e2e-'));
  const listener = net.createServer();
  await new Promise(resolve => listener.listen(0, '127.0.0.1', resolve));
  const port = listener.address().port;
  await new Promise(resolve => listener.close(resolve));
  const password = 'synthetic-safety-doctor-2026';
  const adminPassword = 'synthetic-safety-admin-2026';
  const python = process.env.PYTHON || path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
  const readyFile = path.join(runtime, 'server-ready.json');
  const instanceToken = randomBytes(32).toString('hex');
  const child = spawn(python, ['tests/serve_isolated_app.py'], { cwd: root,
    env: { ...process.env, APP_DATA_DIR: runtime, APP_DB_PATH: path.join(runtime, 'safety.sqlite3'),
      APP_E2E_READY_FILE: readyFile,
      APP_E2E_INSTANCE_TOKEN: instanceToken,
      APP_SYNTHETIC_DEMO_MODE: syntheticFixtureDir ? 'true' : 'false',
      APP_SYNTHETIC_DEMO_FIXTURE_DIR: syntheticFixtureDir || '',
      APP_CORS_ORIGINS: '', DATABASE_URL: '',
      APP_JWT_SECRET: 'synthetic-safety-jwt-secret-2026-10-25',
      APP_PATIENT_PID_HMAC_SECRET: 'synthetic-safety-hmac-secret-2026-10-25',
      APP_DOCTOR_PASSWORD: password, APP_ADMIN_PASSWORD: adminPassword,
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
      if (fs.existsSync(readyFile)) {
        const marker = JSON.parse(fs.readFileSync(readyFile, 'utf8'));
        if (!Number.isSafeInteger(marker.pid) || marker.pid <= 0 || marker.host !== '127.0.0.1'
          || marker.port !== port || marker.runtime !== runtime || marker.instance_token !== instanceToken) {
          throw Error('Isolated server readiness marker mismatch: '
            + JSON.stringify({ marker: { ...marker, instance_token: '<redacted>' },
              expected: { host: '127.0.0.1', port, runtime, instance_token: '<spawned-process-token>' } }));
        }
        try { if ((await fetch(base + '/api/health/live')).ok) { ready = true; break; } } catch {}
      }
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    if (!ready) throw Error('Isolated server did not become ready');
    browser = await chromium.launch({ headless: true,
      executablePath: process.env.CHROME_PATH || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined) });
    return {
      browser,
      base,
      password,
      adminPassword,
      runtime,
      close: async () => {
        const cleanupErrors = [];
        try { await browser.close(); } catch (error) { cleanupErrors.push(error); }
        try {
          await stopChild(child);
          await assertListenerStopped(port);
          removeRuntime(runtime);
        } catch (error) { cleanupErrors.push(error); }
        if (cleanupErrors.length === 1) throw cleanupErrors[0];
        if (cleanupErrors.length > 1) {
          throw new AggregateError(cleanupErrors, 'Browser and isolated server cleanup failed.');
        }
      },
    };
  } catch (error) {
    const cleanupErrors = [];
    try { await browser?.close(); } catch (cleanupError) { cleanupErrors.push(cleanupError); }
    try {
      await stopChild(child);
      await assertListenerStopped(port);
      removeRuntime(runtime);
    } catch (cleanupError) {
      cleanupErrors.push(cleanupError);
    }
    if (cleanupErrors.length) {
      throw new AggregateError([error, ...cleanupErrors], 'Isolated server setup and cleanup both failed.');
    }
    throw error;
  }
};
