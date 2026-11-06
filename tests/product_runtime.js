const assert = require('node:assert/strict');

(async () => {
  global.location = { hash: '#login' };
  Object.defineProperty(global, 'navigator', { value: { onLine: true }, configurable: true });
  const { renderAuth } = await import('../frontend/app/auth.js');
  const { state } = await import('../frontend/app/state.js');
  const { getCasesPage } = await import('../frontend/app/cases.js');
  const html = renderAuth();
  assert.doesNotMatch(html, /demo|minh họa|bản mẫu|thử nghiệm/i);
  assert.match(html, /OVARIAN ULTRASOUND · RUO/);
  assert.match(html, /không dùng để chẩn đoán hoặc chăm sóc bệnh nhân/i);
  state.user = { id: 'runtime-check', role: 'DOCTOR' };
  state.capabilities = {};
  let calls = 0;
  const sourcePatientId = 'SOURCE-PID-CANARY-DO-NOT-PLACE-IN-URL';
  global.fetch = async (url, options) => {
    const requestUrl = new URL(url, 'http://localhost');
    const body = JSON.parse(options.body);
    assert.equal(requestUrl.pathname, '/api/workspace/cases/search');
    assert.equal(requestUrl.search, '');
    assert.equal(requestUrl.href.includes(sourcePatientId), false);
    assert.equal(options.method, 'POST');
    assert.equal(body.search, sourcePatientId);
    assert.equal(body.limit, 100);
    assert.equal(body.offset, 0);
    calls++;
    return new Response('{"items":[],"total":0}', { headers: { 'Content-Type': 'application/json' } });
  };
  assert.deepEqual(await getCasesPage({ search: sourcePatientId }, { limit: 100 }), { items: [], total: 0 });
  assert.equal(calls, 1);
  global.fetch = async () => new Response('{"detail":"Service unavailable"}', { status: 503 });
  await assert.rejects(getCasesPage({}, { limit: 100 }), /Service unavailable/);
  global.fetch = async () => new Response('{}', { headers: { 'Content-Type': 'application/json' } });
  await assert.rejects(getCasesPage({}, { limit: 100 }), {
    message: 'Danh sách ca trả về không đúng hợp đồng phân trang.',
  });
  let requestedOffset;
  global.fetch = async (_url, options) => {
    requestedOffset = JSON.parse(options.body).offset;
    return new Response(JSON.stringify({ items: [{ id: 'last-study' }], total: 10001 }), {
      headers: { 'Content-Type': 'application/json' },
    });
  };
  const lastHistoryPage = await getCasesPage({}, { limit: 100, offset: 10000 });
  assert.equal(lastHistoryPage.total, 10001);
  assert.equal(lastHistoryPage.items[0].study_id, 'last-study');
  assert.equal(requestedOffset, 10000);
  console.log('PASS: authenticated interface, empty API data and service errors without synthetic cases');
})().catch((error) => { console.error(error); process.exitCode = 1; });
