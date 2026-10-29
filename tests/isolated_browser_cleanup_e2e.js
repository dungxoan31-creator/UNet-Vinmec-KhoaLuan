const assert = require('node:assert/strict');
const fs = require('node:fs');
const net = require('node:net');
const { startIsolatedBrowser } = require('./helpers/isolated_browser.cjs');

function probeListener(port) {
  return new Promise(resolve => {
    const socket = net.createConnection({ host: '127.0.0.1', port });
    socket.once('connect', () => {
      socket.destroy();
      resolve('open');
    });
    socket.once('error', error => resolve(error.code === 'ECONNREFUSED' ? 'closed' : 'unknown'));
    socket.setTimeout(1000, () => {
      socket.destroy();
      resolve('unknown');
    });
  });
}

async function main() {
  const server = await startIsolatedBrowser();
  const runtime = server.runtime;
  const port = Number(new URL(server.base).port);
  const closeBrowser = server.browser.close.bind(server.browser);
  let closeAttempted = false;
  server.browser.close = async () => {
    await closeBrowser();
    throw new Error('Injected browser-close acknowledgement failure.');
  };

  try {
    closeAttempted = true;
    await assert.rejects(server.close(), /Injected browser-close acknowledgement failure/);
    assert.equal(fs.existsSync(runtime), false, 'Runtime should be removed only after backend shutdown is verified.');
    assert.equal(await probeListener(port), 'closed', 'The isolated loopback listener must be closed.');
    console.log('PASS: browser-close failure is reported after backend stop, listener verification, and runtime cleanup');
  } catch (error) {
    if (!closeAttempted) {
      try { await server.close(); } catch {}
    }
    throw error;
  }
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
