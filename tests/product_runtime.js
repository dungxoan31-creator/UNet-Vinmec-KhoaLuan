const assert = require('node:assert/strict');

(async () => {
  global.location = { hash: '#login' };
  Object.defineProperty(global, 'navigator', { value: { onLine: true }, configurable: true });
  const { renderAuth } = await import('../frontend/app/auth.js');
  const { state } = await import('../frontend/app/state.js');
  const { getCases } = await import('../frontend/app/cases.js');
  const html = renderAuth();
  assert.doesNotMatch(html, /demo|minh họa|bản mẫu|thử nghiệm/i);
  assert.match(html, /vinmec-logo/);
  state.user = { id: 'runtime-check', role: 'DOCTOR' };
  state.capabilities = {};
  let calls = 0;
  global.fetch = async (url) => {
    assert.equal(url, '/api/cases');
    calls++;
    return new Response('[]', { headers: { 'Content-Type': 'application/json' } });
  };
  assert.deepEqual(await getCases(), []);
  assert.equal(calls, 1);
  global.fetch = async () => new Response('{"detail":"Service unavailable"}', { status: 503 });
  await assert.rejects(getCases(), /Service unavailable/);
  console.log('PASS: authenticated interface, empty API data and service errors without synthetic cases');
})().catch((error) => { console.error(error); process.exitCode = 1; });
