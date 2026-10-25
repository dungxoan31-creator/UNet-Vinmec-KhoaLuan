import test from 'node:test';
import assert from 'node:assert/strict';
import { encode } from '../frontend/app/coordinates.js';
import { isCompleteReviewAck, matchesSubmittedReview, reviewWarnings, consistencyKey, hasUnresolvedReviewWarning } from '../frontend/app/review-content.js';

const body = side => ({ image_id: side, prediction_id: 'p-' + side, doctor_action: 'ACCEPTED_RAW' });
const bodies = ['L', 'R'].map(body);
const ack = () => ({ status: 'SUCCESS', study_id: 'study', review_revision: 4,
  reviews: bodies.map(row => ({ ...row, review_id: 'review-' + row.image_id })) });
test('save ACK must confirm the exact study, revision, image set and prediction/action', () => {
  assert.equal(isCompleteReviewAck(ack(), 'study', 3, bodies), true);
  for (const mutate of [
    result => { result.study_id = 'other'; }, result => { result.review_revision = 3; },
    result => { result.reviews.pop(); }, result => { result.reviews[1] = result.reviews[0]; },
    result => { result.reviews[1].prediction_id = 'foreign'; },
    result => { result.reviews[1].review_id = ''; },
    result => { result.reviews[1].doctor_action = 'REJECTED_ALL'; },
  ]) {
    const result = ack(); mutate(result);
    assert.equal(isCompleteReviewAck(result, 'study', 3, bodies), false);
  }
});
test('content changed while a save was pending is never considered clean', () => {
  const mask = new Uint8Array(512 * 512); mask[50] = 1;
  const image = { image_id: 'L', prediction: { prediction_id: 'p-L' }, mask,
    notes: 'original', orads: '', morphology: '', morphologyDesc: '' };
  const submitted = { ...body('L'), verified_mask_rle: encode(mask), clinical_notes: 'original', lesion_type: 'Chưa đánh giá' };
  assert.equal(matchesSubmittedReview(image, submitted), true);
  image.mask[50] = 0;
  assert.equal(matchesSubmittedReview(image, submitted), false, 'mask changes matter as much as text');
  image.mask[50] = 1; image.notes = 'new note';
  assert.equal(matchesSubmittedReview(image, submitted), false);
});
test('clinical disagreement requires an acknowledgement tied to exact side/content', () => {
  const image = { image_id: 'L', notes: 'Nhận định O-RADS 4', orads: 'O-RADS 2' };
  assert.equal(reviewWarnings(image).length, 1);
  assert.equal(hasUnresolvedReviewWarning(image), true);
  image.consistencyAcknowledgement = consistencyKey(image);
  assert.equal(hasUnresolvedReviewWarning(image), false);
  image.notes = 'Nhận định O-RADS 5';
  assert.equal(hasUnresolvedReviewWarning(image), true);
  image.notes = 'Mô tả [bác sĩ ghi nhận kích thước]'; image.consistencyAcknowledgement = consistencyKey(image);
  assert.equal(hasUnresolvedReviewWarning(image), true, 'a placeholder cannot be acknowledged as complete');
  assert.deepEqual(reviewWarnings({ notes: 'Mô tả chưa đủ để phân tầng', orads: '' }), []);
});
