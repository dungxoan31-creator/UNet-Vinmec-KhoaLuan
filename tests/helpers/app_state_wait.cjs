/* Poll app state from Node so asynchronous predicates cannot resolve as truthy Promise objects. */
async function readAppSnapshot(page, { maskIndices = [] } = {}) {
  return page.evaluate(async indices => {
    const { state } = await import('/static/app/state.js');
    const selector = document.querySelector('#viewerImageSelect');
    return {
      busy: state.busy,
      online: state.online,
      side: state.side,
      route: state.route,
      user: state.user ? { id: state.user.id, role: state.user.role, username: state.user.username } : null,
      editing: state.editing ? { caseId: state.editing.caseId, allowed: state.editing.allowed,
        leaseToken: Boolean(state.editing.leaseToken) } : null,
      dirty: state.dirty,
      draftConflict: state.draftConflict ? { caseId: state.draftConflict.caseId } : null,
      pendingReview: Boolean(state.pendingReview),
      case: state.case ? {
        study_id: state.case.study_id,
        study_code: state.case.study_code,
        patient_id: state.case.patient_id,
        status: state.case.status,
        version: state.case.version,
        review_revision: state.case.review_revision,
        images: state.case.images?.map(image => ({
          image_id: image.image_id,
          laterality: image.laterality,
          seen: image.seen,
          notes: image.notes,
          prediction_id: image.prediction?.prediction_id,
          review_id: image.review?.review_id,
          mask_samples: Object.fromEntries(indices.map(index => [index, Number(image.mask?.[index] ?? 0)])),
          mask_pixels: indices.includes(-1)
            ? image.mask?.reduce((sum, value) => sum + Number(Boolean(value)), 0) ?? null
            : undefined,
        })),
      } : null,
      dom: {
        hash: location.hash,
        navigator_online: navigator.onLine,
        selected_image_id: selector?.value ?? null,
        selector_disabled: selector?.disabled ?? null,
        side_label: document.querySelector('#sideLabel')?.textContent ?? null,
        save_review_disabled: document.querySelector('[data-action="save-review"]')?.disabled ?? null,
        measurement_d1: document.querySelector('#d1')?.textContent ?? null,
        case_search_present: Boolean(document.querySelector('#caseSearch')),
      },
    };
  }, maskIndices);
}

async function waitForAppState(page, predicate, {
  timeout = 30000,
  stableMs = 0,
  intervalMs = 50,
  message = 'app state',
  maskIndices = [],
} = {}) {
  const deadline = Date.now() + timeout;
  let stableSince = null;
  let lastSnapshot = null;
  while (Date.now() < deadline) {
    lastSnapshot = await readAppSnapshot(page, { maskIndices });
    if (predicate(lastSnapshot)) {
      stableSince ??= Date.now();
      if (Date.now() - stableSince >= stableMs) return lastSnapshot;
    } else {
      stableSince = null;
    }
    await page.waitForTimeout(intervalMs);
  }
  throw new Error(`Timed out waiting for ${message}: ${JSON.stringify(lastSnapshot)}`);
}

module.exports = { readAppSnapshot, waitForAppState };
