function intakeSession() {
    return {user: currentUser, role: currentRole, token: sessionStorage.getItem('ovarian_ai_access_token')};
}
function sameIntakeSession(session) {
    return !!session.user && !!session.token && currentUser === session.user &&
        currentRole === session.role && sessionStorage.getItem('ovarian_ai_access_token') === session.token;
}
function syncIntakeControls() {
    const busy = Boolean(currentCase.processing || currentCase.saving || currentCase.selecting);
    const locked = busy || Boolean(currentCase.study_id);
    for (const id of ['intakePid', 'intakeReason']) if ($(id)) $(id).disabled = locked;
    document.querySelectorAll('input[name="ovarySide"]').forEach(input => input.disabled = locked);
}
function reflectIntakeMetadata() {
    if ($('intakePid')) $('intakePid').value = currentCase.patient_id || '';
    document.querySelectorAll('input[name="ovarySide"]').forEach(input =>
        input.checked = input.value === (currentCase.ovary_side || 'UNKNOWN'));
    const reason = $('intakeReason'), value = currentCase.clinical_indication || 'Khác / chưa ghi nhận';
    if (reason) {
        if (!Array.from(reason.options).some(option => option.value === value)) {
            const option = document.createElement('option');
            option.value = option.textContent = value;
            option.dataset.intakeAdded = 'true';
            reason.append(option);
        }
        reason.value = value;
    }
    syncIntakeControls();
}
function readIntakeMetadata() {
    const pid = ($('intakePid')?.value || '').trim();
    if (pid.length > 64) throw new Error('PID tối đa 64 ký tự.');
    const side = document.querySelector('input[name="ovarySide"]:checked')?.value || 'UNKNOWN';
    if (!['RIGHT', 'LEFT', 'BOTH', 'UNKNOWN'].includes(side)) throw new Error('Bên khảo sát không hợp lệ.');
    const today = new Date();
    return {
        patient_id: pid || currentCase.patient_id || 'BN-' + crypto.randomUUID().toUpperCase(),
        ovary_side: side,
        clinical_indication: $('intakeReason')?.value || 'Khác / chưa ghi nhận',
        study_date: today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') +
            '-' + String(today.getDate()).padStart(2, '0')
    };
}
function resetIntakeForm() {
    if (currentCase.study_id || currentCase.processing || currentCase.saving) return;
    if ($('intakePid')) $('intakePid').value = '';
    document.querySelectorAll('input[name="ovarySide"]').forEach(input => input.checked = input.value === 'UNKNOWN');
    const reason = $('intakeReason');
    if (reason) {
        Array.from(reason.options).filter(option => option.dataset.intakeAdded === 'true').forEach(option => option.remove());
        reason.value = 'Khác / chưa ghi nhận';
    }
    for (const key of ['patient_id', 'ovary_side', 'clinical_indication', 'study_date']) delete currentCase[key];
    syncIntakeControls();
}
