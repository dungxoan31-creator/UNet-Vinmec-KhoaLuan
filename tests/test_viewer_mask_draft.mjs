import assert from 'node:assert/strict';
import test from 'node:test';

const values = new Map();
globalThis.localStorage = {
  getItem: key => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, String(value)),
  removeItem: key => values.delete(key),
};

const {
  clearDraft,
  draftKey,
  maskDraftKey,
  restoreDraft,
  restoreMaskDrafts,
  saveDraft,
  saveMaskDraft,
  state,
} = await import('../frontend/app/state.js?mask-draft-test');

test('per-image RLE drafts restore only against the matching study revision and clear after acknowledgement', () => {
  const mask = new Uint8Array(512 * 512);
  mask[17] = 1;
  mask[8193] = 1;
  const study = {
    study_id: 'study-mask-draft',
    version: 4,
    images: [{ image_id: 'image-left', laterality: 'L', review: null, mask }],
  };
  state.user = { id: 'doctor-mask-draft' };
  state.case = study;
  state.draftConflict = null;
  state.dirty = false;

  assert.equal(saveMaskDraft(study, study.images[0]), true);
  const key = maskDraftKey(study.study_id, 'image-left');
  const saved = JSON.parse(values.get(key));
  assert.deepEqual(saved.mask_rle.shape, [512, 512]);
  assert.equal(saved.image_id, 'image-left');

  const reopened = {
    ...study,
    images: [{ image_id: 'image-left', laterality: 'L', review: null, mask: new Uint8Array(512 * 512) }],
  };
  assert.deepEqual(restoreMaskDrafts(reopened), ['L']);
  assert.equal(reopened.images[0].mask[17], 1);
  assert.equal(reopened.images[0].mask[8193], 1);
  assert.equal(state.dirty, true);

  const staleRevision = { ...reopened, version: 5, images: [{ ...reopened.images[0], mask: new Uint8Array(512 * 512) }] };
  assert.deepEqual(restoreMaskDrafts(staleRevision), []);
  assert.equal(staleRevision.images[0].mask.some(Boolean), false);

  saveDraft();
  const fullDraft = JSON.parse(values.get(draftKey(study.study_id)));
  assert.equal(Object.hasOwn(fullDraft.images[0], 'mask'), false,
    'the per-side RLE entry is the sole new mask snapshot');
  clearDraft();
  assert.equal(values.has(draftKey(study.study_id)), false);
  assert.equal(values.has(key), false);
});

test('multiple stills from one side retain separate masks and clinician calipers', () => {
  values.clear();
  const leftA = new Uint8Array(512 * 512);
  const leftB = new Uint8Array(512 * 512);
  leftA[1] = 1;
  leftB[2] = 1;
  const study = {
    study_id: 'multi-image-study',
    version: 2,
    images: [
      { image_id: 'left-a', laterality: 'L', width: 640, height: 480, review: null, mask: leftA,
        manualCalipers: [{ label: 'D1', points: [[20, 30], [120, 30]] }] },
      { image_id: 'left-b', laterality: 'L', width: 640, height: 480, review: null, mask: leftB,
        manualCalipers: [{ label: 'D2', points: [[40, 50], [40, 90]] }] },
    ],
  };
  state.user = { id: 'doctor-mask-draft' };
  state.case = study;
  state.draftConflict = null;
  assert.equal(saveMaskDraft(study, study.images[0]), true);
  assert.equal(saveMaskDraft(study, study.images[1]), true);
  assert.notEqual(values.get(maskDraftKey(study.study_id, 'left-a')), values.get(maskDraftKey(study.study_id, 'left-b')));
  saveDraft();

  const reopened = {
    ...study,
    images: study.images.map(image => ({
      ...image,
      mask: new Uint8Array(512 * 512),
      manualCalipers: [],
    })),
  };
  assert.deepEqual(restoreMaskDrafts(reopened), ['L:left-a', 'L:left-b']);
  assert.equal(reopened.images[0].mask[1], 1);
  assert.equal(reopened.images[1].mask[2], 1);
  assert.equal(restoreDraft(reopened), true);
  assert.deepEqual(reopened.images[0].manualCalipers, [{ label: 'D1', points: [[20, 30], [120, 30]] }]);
  assert.deepEqual(reopened.images[1].manualCalipers, [{ label: 'D2', points: [[40, 50], [40, 90]] }]);

  const invalid = JSON.parse(values.get(draftKey(study.study_id)));
  invalid.images[0].manual_calipers = [{ label: 'D1', points: [[20, 30], [640, 30]] }];
  values.set(draftKey(study.study_id), JSON.stringify(invalid));
  assert.equal(restoreDraft(reopened), false, 'out-of-bounds local calipers cannot be restored');
});

test('a mask draft from another clinician is never restored into the shared case', () => {
  values.clear();
  const study = {
    study_id: 'shared-workstation-study',
    version: 7,
    images: [{ image_id: 'shared-image', laterality: 'L', review: null, mask: new Uint8Array(512 * 512) }],
  };
  state.draftConflict = null;
  state.dirty = false;
  state.user = { id: 'doctor-a' };
  study.images[0].mask[321] = 1;
  assert.equal(saveMaskDraft(study, study.images[0]), true);
  const doctorAKey = maskDraftKey(study.study_id, 'shared-image');

  state.user = { id: 'doctor-b' };
  const doctorBKey = maskDraftKey(study.study_id, 'shared-image');
  const reopened = {
    ...study,
    images: [{ ...study.images[0], mask: new Uint8Array(512 * 512) }],
  };
  assert.deepEqual(restoreMaskDrafts(reopened), [],
    'a second clinician must not inherit an uncommitted mask draft for the same case');
  assert.equal(reopened.images[0].mask.some(Boolean), false);
  assert.notEqual(doctorAKey, doctorBKey);
  state.case = study;
  clearDraft();
  assert.equal(values.has(doctorAKey), true,
    'clearing the current clinician draft must not remove another clinician’s mask draft');
});

test('legacy unscoped mask drafts are preserved but flagged and never restored', () => {
  values.clear();
  const study = {
    study_id: 'legacy-mask-study',
    version: 3,
    images: [{ image_id: 'legacy-image', laterality: 'L', review: null, mask: new Uint8Array(512 * 512) }],
  };
  state.user = { id: 'doctor-a' };
  state.case = study;
  study.images[0].mask[900] = 1;
  assert.equal(saveMaskDraft(study, study.images[0]), true);
  const saved = JSON.parse(values.get(maskDraftKey(study.study_id, 'legacy-image')));
  values.set(`draft_mask_${study.study_id}_legacy-image`, JSON.stringify({ ...saved, schema_version: 1 }));

  state.user = { id: 'doctor-b' };
  const reopened = {
    ...study,
    images: [{ ...study.images[0], mask: new Uint8Array(512 * 512) }],
  };
  assert.deepEqual(restoreMaskDrafts(reopened), []);
  assert.equal(reopened.images[0].mask.some(Boolean), false);
  assert.equal(state.unattributedMaskDraft, true,
    'the viewer must warn that an old draft exists but has no safe owner attribution');
  assert.equal(values.has(`draft_mask_${study.study_id}_legacy-image`), true,
    'the unowned legacy data is not silently deleted');
  state.draftConflict = { caseId: study.study_id };
  assert.deepEqual(restoreMaskDrafts(reopened), []);
  assert.equal(state.unattributedMaskDraft, true,
    'a separate local-draft conflict must not suppress the legacy ownership warning');
});
