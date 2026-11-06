import assert from 'node:assert/strict';
import test from 'node:test';
import { can, role, state } from '../frontend/app/state.js';

test('only the senior reviewer role is granted the evaluation screen in the frontend', () => {
  state.user = { role: 'SENIOR' };
  assert.equal(role(), 'TK');
  assert.equal(can('evaluation'), true);

  for (const userRole of ['DOCTOR', 'ADMIN', 'TECHNICIAN']) {
    state.user = { role: userRole };
    assert.equal(can('evaluation'), false, `${userRole} must not access evaluation`);
  }

  state.user = null;
  assert.equal(can('evaluation'), false);
});
