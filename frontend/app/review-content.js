import { encode } from "./coordinates.js";

function nonemptyClinicalValue(value, key) {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  if (!normalized) return null;
  if (key === "lesion_type" && ["chưa đánh giá", "unspecified"].includes(normalized.toLocaleLowerCase("vi")))
    return null;
  return normalized;
}

export function clinicianDiagnosisOverrides(image) {
  const previous = image?.review || {};
  const previousFeedback = previous.hitl_feedback || {};
  const currentValues = {
    lesion_type: image?.morphology,
    orads: image?.orads,
    morphology_description: image?.morphologyDesc,
  };
  const previousValues = {
    lesion_type: previous.lesion_type,
    orads: previous.orads || previous.orads_score || previousFeedback.orads || previousFeedback.orads_score,
    morphology_description: previous.morphology_description || previousFeedback.morphologyDesc || previousFeedback.morphology_description,
  };
  const overrides = {};
  for (const [key, currentValue] of Object.entries(currentValues)) {
    const current = nonemptyClinicalValue(currentValue, key);
    const baseline = nonemptyClinicalValue(previousValues[key], key);
    if (current !== baseline && (current !== null || baseline !== null))
      overrides[key] = current;
  }
  return overrides;
}

export function matchesSubmittedReview(image, body) {
  return image.image_id === body.image_id &&
    image.prediction?.prediction_id === body.prediction_id &&
    JSON.stringify(encode(image.mask)) === JSON.stringify(body.verified_mask_rle) &&
    JSON.stringify(image.manualCalipers || []) === JSON.stringify(body.manual_calipers || []) &&
    (image.orads || "") === (body.orads || "") &&
    (image.morphology || "Chưa đánh giá") === (body.lesion_type || "Chưa đánh giá") &&
    (image.morphologyDesc || "") === (body.morphology_description || "") &&
    (image.notes || "") === (body.clinical_notes || "");
}

export function isCompleteReviewAck(result, studyId, expectedRevision, bodies) {
  return result?.status === "SUCCESS" && result.study_id === studyId &&
    result.review_revision === expectedRevision + 1 && Array.isArray(result.reviews) &&
    result.reviews.length === bodies.length &&
    new Set(result.reviews.map(review => review.review_id)).size === bodies.length &&
    new Set(result.reviews.map(review => review.image_id)).size === bodies.length &&
    bodies.every(body => result.reviews.some(review =>
      typeof review.review_id === "string" && review.review_id.length > 0 &&
      review.image_id === body.image_id && review.prediction_id === body.prediction_id &&
      review.doctor_action === body.doctor_action));
}

export function reviewWarnings(image) {
  const text = `${image?.morphologyDesc || ""}\n${image?.notes || ""}`;
  const notesCategories = [...text.matchAll(/O[\s-]*RADS\s*([0-5])\b/giu)].map(match => match[1]);
  const selected = image?.orads?.match(/O[\s-]*RADS\s*([0-5])\b/iu)?.[1];
  const warnings = [];
  if (notesCategories.some(category => !selected || category !== selected))
    warnings.push("Ghi chú/mô tả có O-RADS khác hoặc chưa có lựa chọn tương ứng. Kiểm tra nhận định và bối cảnh trước khi lưu.");
  if (/\[(?:cần|bác sĩ)[^\]]*\]/iu.test(text))
    warnings.push("Mẫu mô tả còn chỗ trống cần bác sĩ điền hoặc xóa trước khi lưu.");
  return warnings;
}

export function consistencyKey(image) {
  return JSON.stringify([image?.image_id, image?.orads || "", image?.morphologyDesc || "", image?.notes || ""]);
}

export function hasUnresolvedReviewWarning(image) {
  const warnings = reviewWarnings(image);
  // Placeholders must be resolved, not acknowledged as complete observations.
  return warnings.length > 0 && (warnings.some(text => text.includes("chỗ trống")) ||
    image.consistencyAcknowledgement !== consistencyKey(image));
}
