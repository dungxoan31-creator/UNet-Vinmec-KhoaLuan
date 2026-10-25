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
  global.fetch = async (url, options) => {
    const requestUrl = new URL(url, 'http://localhost');
    const body = JSON.parse(options.body);
    assert.equal(requestUrl.pathname, '/api/cases/search');
    assert.equal(requestUrl.search, '');
    assert.equal(options.method, 'POST');
    assert.equal(body.limit, 100);
    assert.equal(body.offset, 0);
    calls++;
    return new Response('[]', { headers: { 'Content-Type': 'application/json' } });
  };
  assert.deepEqual(await getCases(), []);
  assert.equal(calls, 1);
  global.fetch = async () => new Response('{"detail":"Service unavailable"}', { status: 503 });
  await assert.rejects(getCases(), /Service unavailable/);
  global.fetch = async () => new Response('{}', { headers: { 'Content-Type': 'application/json' } });
  await assert.rejects(getCases(), {
    message: 'Danh sách ca trả về không đúng hợp đồng phân trang.',
  });
  let oversizedCalls = 0;
  global.fetch = async () => {
    oversizedCalls++;
    const page = Array.from({ length: 100 }, (_, index) => ({ id: `${oversizedCalls}-${index}` }));
    return new Response(JSON.stringify(page), { headers: { 'Content-Type': 'application/json' } });
  };
  await assert.rejects(getCases(), {
    message: 'Danh sách quá lớn để tổng hợp trên thiết bị.',
  });
  assert.equal(oversizedCalls, 101);
  console.log('PASS: authenticated interface, empty API data and service errors without synthetic cases');
})().catch((error) => { console.error(error); process.exitCode = 1; });
