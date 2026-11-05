// Move existing controls without cloning them or changing their data bindings.
export function organizeAssessment(root) {
  const panel = root.querySelector('#clinicalPanel');
  if (!panel) return;
  const groups = [
    ['lesionFeatures', 'Đánh giá tổn thương', ['#iotaMorphology', '.clinical-morphology-chips', '#oradsScore', '#oradsHelp', '#adnexMount']],
    ['doctorConclusion', 'Ghi chú lâm sàng', ['#morphology', '#notes', '#localDictation']],
    ['aiAnalysis', 'Phân tích hình ảnh AI', ['#imageClassification', '#segmentationState', '#segmentationDependencyWarning', '#reviewContentWarning', '.clinical-actions']],
  ];
  for (const heading of panel.querySelectorAll(':scope > h3')) heading.remove();
  for (const [id, title, selectors] of groups) {
    const group = document.createElement('section');
    group.className = 'assessment-group'; group.id = id;
    const heading = document.createElement('h3'); heading.textContent = title;
    group.append(heading);
    for (const selector of selectors) {
      const element = panel.querySelector(selector);
      if (!element) continue;
      if (selector === '.clinical-morphology-chips') {
        const label = document.createElement('span'); label.className = 'assessment-field-label'; label.textContent = 'Đặc điểm tổn thương';
        group.append(label);
        element.setAttribute('role', 'group'); element.setAttribute('aria-label', 'Đặc điểm tổn thương');
      }
      group.append(element.closest('label.field') || (selector === '#imageClassification' ? element.closest('details') : element));
    }
    panel.append(group);
  }
  // Existing viewer controllers retain their state bindings without exposing
  // the removed technical/research controls as an interactive UI section.
  const internal = document.createElement('div'); internal.id = 'viewerInternalData';
  internal.hidden = true;
  internal.setAttribute('aria-hidden', 'true');
  internal.setAttribute('inert', '');
  const classifierProvenance = document.createElement('p'); classifierProvenance.id = 'classificationProvenance'; classifierProvenance.className = 'small mono';
  internal.append(classifierProvenance);
  for (const selector of ['#modelHash', '#historyList', '#researchCandidateMount', '#regionReviewMount', '#regionCaliperStatus', '#regionCaliperRetry', '.timeline', '.clinical-mask-note', '#follicleReference']) {
    const element = panel.querySelector(selector);
    if (element) internal.append(element.closest('details') || element);
  }
  panel.append(internal);
  const save = root.querySelector('[data-action="save-review"]');
  if (save) {
    save.classList.remove('quiet'); save.classList.add('primary');
    panel.querySelector('#aiAnalysis').append(save);
  }
}
