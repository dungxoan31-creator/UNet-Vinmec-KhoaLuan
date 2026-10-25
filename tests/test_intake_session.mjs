import test from 'node:test';
import assert from 'node:assert/strict';
import { createIntakeSession, createDemoPatientStore, planBilateralDrop } from '../frontend/app/intake-session.js';
import { suggestLaterality } from '../frontend/app/laterality-hint.js';

test('replacement, removal, disposal and account/token changes invalidate pending metadata', () => {
  let account = 'doctor-A:token-1';
  const intake = createIntakeSession(() => account);
  const first = intake.select('L', { name: 'first.png' });
  const right = intake.select('R', { name: 'right.png' });
  const replacement = intake.select('L', { name: 'second.png' });
  assert.equal(first.signal.aborted, true);
  assert.equal(first.current(), false);
  assert.equal(right.current(), true);
  assert.equal(replacement.current(), true);
  intake.remove('L');
  assert.equal(replacement.current(), false);
  account = 'doctor-A:token-2';
  assert.equal(right.current(), false, 'same user with a changed token is another session');
  intake.dispose();
  assert.equal(right.signal.aborted, true);
  assert.equal(intake.active(), false);
});

test('an old intake cannot regain write access after another patient is selected', () => {
  const old = createIntakeSession(() => 'doctor');
  const request = old.select('L', {});
  old.dispose();
  const current = createIntakeSession(() => 'doctor');
  assert.equal(request.current(), false);
  assert.equal(current.select('L', {}).current(), true);
});

test('only a distinct L/R pair can propose automatic bilateral allocation', () => {
  for (const names of [['scan-left.png', 'scan-right.png'], ['scan-right.png', 'scan-left.png']]) {
    const plan = planBilateralDrop(names.map(name => ({ name })), suggestLaterality);
    assert.deepEqual(plan.map(row => row.side), names[0].includes('left') ? ['L', 'R'] : ['R', 'L']);
    assert.equal(plan.some(row => row.needsConfirmation), false);
  }
  for (const names of [['left-1.png', 'left-2.png'], ['right-1.png', 'right-2.png'],
    ['a.png', 'b.png'], ['left-right.png', 'right.png'], ['left.png', 'unknown.png']]) {
    const plan = planBilateralDrop(names.map(name => ({ name })), suggestLaterality);
    assert.equal(plan.every(row => row.needsConfirmation), true, names.join(','));
    assert.deepEqual(plan.map(row => row.file.name), names, 'neither file is discarded');
  }
});

test('quota/security failures preserve session rows and isolate account namespaces', () => {
  const seeds = [{ pid: 'seed', name: 'Synthetic', age: 20 }];
  const blocked = () => { throw new DOMException('denied', 'SecurityError'); };
  const store = createDemoPatientStore(seeds, blocked);
  assert.equal(store.read('A').length, 1);
  assert.equal(store.isTransient('A'), true);
  const added = { pid: 'new', name: 'Synthetic new', age: 30 };
  store.save('A', [...store.read('A'), added]);
  assert.equal(store.read('A').length, 2);
  assert.equal(store.read('B').length, 1);
  assert.equal(seeds.length, 1, 'fallback must not mutate the global seeds');
});

test('malformed saved rows fall back safely and a subsequent successful write is durable', () => {
  const items = new Map([['A', '[null]']]);
  const store = createDemoPatientStore([{ pid: 'seed', name: 'Synthetic', age: 20 }], () => ({
    getItem: key => items.get(key), setItem: (key, value) => items.set(key, value),
  }));
  assert.equal(store.read('A')[0].pid, 'seed');
  assert.equal(store.isTransient('A'), false);
  assert.equal(JSON.parse(items.get('A'))[0].pid, 'seed');
});
