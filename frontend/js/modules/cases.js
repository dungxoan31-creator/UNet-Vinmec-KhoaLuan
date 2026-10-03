/**
 * MODULE: CASES.JS
 */


async function loadDashboardStats() {
            try {
                const resp = await fetch(`${API_BASE}/api/stats`);
                if (resp.ok) {
                    const data = await resp.json();
                    const totalVal = data.total_cases_received ?? data.total_images_collected ?? 0;
                    const signedVal = data.doctor_approved_cases ?? data.ground_truth_confirmed ?? 0;
                    const pendingVal = data.pending_evaluation_cases !== undefined ? data.pending_evaluation_cases : (totalVal - signedVal);
                    const rateVal = signedVal ? `${data.ai_consensus_rate_pct ?? data.doctor_acceptance_rate_pct ?? 0}%` : 'N/A';

                    // Update Doctor Dashboard Cards
                    const elTotal = document.getElementById('statTotalImgs');
                    const elSigned = document.getElementById('statGtConfirmed');
                    const elPending = document.getElementById('statPending');
                    const elRate = document.getElementById('statAcceptRate');

                    if (elTotal) elTotal.innerText = totalVal;
                    if (elSigned) elSigned.innerText = signedVal;
                    if (elPending) elPending.innerText = pendingVal;
                    if (elRate) elRate.innerText = rateVal;

                    // Update Admin Dashboard Cards
                    const elAdmTotal = document.getElementById('adminStatTotal');
                    const elAdmSigned = document.getElementById('adminStatSigned');
                    const elAdmPending = document.getElementById('adminStatPending');
                    const elAdmRate = document.getElementById('adminStatConsensus');

                    if (elAdmTotal) elAdmTotal.innerText = totalVal;
                    if (elAdmSigned) elAdmSigned.innerText = signedVal;
                    if (elAdmPending) elAdmPending.innerText = pendingVal;
                    if (elAdmRate) elAdmRate.innerText = rateVal;
                }
            } catch (err) {
                console.error("Stats live sync notice:", err);
            }
        }

async function loadDashboardCases() {
            try {
                const resp = await fetch(`${API_BASE}/api/cases`);
                if (resp.ok) {
                    const cases = await resp.json();
                    renderRecentCasesTable(cases);
                }
            } catch (err) {
                console.error(err);
            }
        }

function renderRecentCasesTable(cases) {
    const tbodies = [
        document.getElementById('recentCasesTableBody'),
        document.getElementById('dashboardRecentCasesTableBody')
    ].filter(Boolean);
    if (tbodies.length === 0) return;

    if (!cases || cases.length === 0) {
        tbodies.forEach(tbody => {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--vm-text-muted); padding: 32px 16px;">Chưa có ca khám nào. Hãy bấm "+ Phân Tích Ca Mới" để bắt đầu.</td></tr>`;
        });
        return;
    }

    const html = cases.slice(0, 8).map(c => {
        const initials = (c.patient_id || 'BN').replace(/[^a-zA-Z0-9]/g, '').slice(0, 2).toUpperCase() || 'BN';
        return `
        <tr>
            <td><strong class="mono-code">${c.study_code || '---'}</strong></td>
            <td>
                <div class="patient-cell">
                    <div class="patient-avatar">${initials}</div>
                    <div class="patient-info">
                        <span class="patient-id">${c.patient_id || 'Chưa định danh'}</span>
                        ${c.patient_age ? `<span class="patient-sub">${c.patient_age} tuổi</span>` : ''}
                    </div>
                </div>
            </td>
            <td><span style="color: var(--vm-text-muted);">${c.study_date || '---'}</span></td>
            <td>
                <span class="badge ${c.status === 'ANALYZED' || c.status === 'REVIEWED' ? 'badge-cyan' : 'badge-neutral'}">
                    ${c.status === 'ANALYZED' || c.status === 'REVIEWED' ? '✓ Đã tạo' : 'Chưa có'}
                </span>
            </td>
            <td>
                <span class="badge ${c.status === 'REVIEWED' ? 'badge-success' : 'badge-neutral'}">
                    ${c.status === 'REVIEWED' ? '✓ Đã xác nhận' : 'Chưa có'}
                </span>
            </td>
            <td>
                <span class="badge ${c.status === 'REVIEWED' ? 'badge-success' : (c.status === 'ANALYZED' ? 'badge-info' : 'badge-warning')}">
                     ${c.status === 'REVIEWED' ? '✓ Đã xác nhận mask' : (c.status === 'ANALYZED' ? '⚡ Đã chạy AI' : '⏳ Chờ phân tích')}
                </span>
            </td>
            <td>
                <button class="btn btn-sm btn-action-cell" onclick="openCaseDetailModal('${c.id}')">
                    👁️ Chi tiết
                </button>
            </td>
        </tr>
    `}).join('');

    tbodies.forEach(tbody => {
        tbody.innerHTML = html;
    });
}

function selectOvarySide(side) {
    const tabR = document.getElementById('tabOvaryRight');
    const tabL = document.getElementById('tabOvaryLeft');
    const inputSide = document.getElementById('inputActiveOvarySide');
    if (!tabR || !tabL || !inputSide) return;

    inputSide.value = side;
    if (side === 'RIGHT') {
        tabR.style.border = '2px solid var(--vm-blue)';
        tabR.style.background = '#eff6ff';
        tabR.style.color = 'var(--vm-blue)';
        tabL.style.border = '1px solid var(--vm-border)';
        tabL.style.background = '#ffffff';
        tabL.style.color = 'var(--vm-text-dark)';
    } else {
        tabL.style.border = '2px solid var(--vm-blue)';
        tabL.style.background = '#eff6ff';
        tabL.style.color = 'var(--vm-blue)';
        tabR.style.border = '1px solid var(--vm-border)';
        tabR.style.background = '#ffffff';
        tabR.style.color = 'var(--vm-text-dark)';
    }
}

async function handleCreateCaseSubmit(e) {
            e.preventDefault();
            const pid = document.getElementById('inputPatientId').value.trim();
            if (!pid) {
                document.getElementById('errPatientId').style.display = 'block';
                return;
            }
            document.getElementById('errPatientId').style.display = 'none';

            const activeOvarySide = document.getElementById('inputActiveOvarySide') ? document.getElementById('inputActiveOvarySide').value : 'RIGHT';
            const contralateralStatus = document.getElementById('selectContralateralStatus') ? document.getElementById('selectContralateralStatus').value : 'NOT_VISUALIZED';

            const payload = {
                patient_id: pid,
                study_code: document.getElementById('inputStudyCode').value.trim() || null,
                study_date: document.getElementById('inputStudyDate').value || new Date().toISOString().split('T')[0],
                patient_age: document.getElementById('inputPatientAge').value,
                active_ovary_side: activeOvarySide,
                contralateral_status: contralateralStatus,
                clinical_notes: document.getElementById('inputClinicalNotes').value.trim()
            };

            try {
                const resp = await fetch(`${API_BASE}/api/cases`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!resp.ok) throw new Error("Lỗi khi tạo ca khám");
                const data = await resp.json();

                if (typeof currentCase === 'undefined' || !currentCase) {
                    window.currentCase = {};
                }

                currentCase.study_id = data.study_id;
                currentCase.study_code = data.study_code;
                currentCase.patient_id = data.patient_id;
                currentCase.patient_age = payload.patient_age;
                currentCase.study_date = data.study_date;
                currentCase.ovary_side = data.ovary_side || activeOvarySide;
                currentCase.contralateral_status = data.contralateral_status || contralateralStatus;
                currentCase.clinical_notes = payload.clinical_notes;

                showToast("✓ Đã tạo ca khám. Hãy chọn ảnh siêu âm!");
                navigateTo('upload');
            } catch (err) {
                showToast("Lỗi khi tạo ca khám: " + err.message, false);
            }
        }

async function loadHistoryTable() {
            try {
                const search = document.getElementById('histSearchInput').value.trim();
                const status = document.getElementById('histStatusFilter').value;
                const date = document.getElementById('histDateFilter').value;

                let url = `${API_BASE}/api/cases?`;
                if (search) url += `search=${encodeURIComponent(search)}&`;
                if (status) url += `status=${encodeURIComponent(status)}&`;
                if (date) url += `date=${encodeURIComponent(date)}&`;

                const resp = await fetch(url);
                if (resp.ok) {
                    const cases = await resp.json();
                    renderHistoryTable(cases);
                }
            } catch (err) {
                console.error(err);
            }
        }

function filterHistory() {
            loadHistoryTable();
        }

function resetHistoryFilters() {
            document.getElementById('histSearchInput').value = '';
            document.getElementById('histStatusFilter').value = 'ALL';
            document.getElementById('histDateFilter').value = '';
            loadHistoryTable();
        }

function renderHistoryTable(cases) {
    const tbody = document.getElementById('historyTableBody');
    if (!tbody) return;
    if (!cases || cases.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--vm-text-muted); padding: 32px 16px;">Không tìm thấy ca khám phù hợp với bộ lọc.</td></tr>`;
        return;
    }

    tbody.innerHTML = cases.map(c => {
        const initials = (c.patient_id || 'BN').replace(/[^a-zA-Z0-9]/g, '').slice(0, 2).toUpperCase() || 'BN';
        return `
        <tr>
            <td><strong class="mono-code">${c.study_code || '---'}</strong></td>
            <td>
                <div class="patient-cell">
                    <div class="patient-avatar">${initials}</div>
                    <div class="patient-info">
                        <span class="patient-id">${c.patient_id || 'Chưa định danh'}</span>
                        ${c.patient_age ? `<span class="patient-sub">${c.patient_age} tuổi</span>` : ''}
                    </div>
                </div>
            </td>
            <td><span style="color: var(--vm-text-muted);">${c.study_date || '---'}</span></td>
            <td>
                <span class="badge ${c.status === 'ANALYZED' || c.status === 'REVIEWED' ? 'badge-cyan' : 'badge-neutral'}">
                    ${c.status === 'ANALYZED' || c.status === 'REVIEWED' ? '✓ Đã tạo' : 'Chưa có'}
                </span>
            </td>
            <td>
                <span class="badge ${c.status === 'REVIEWED' ? 'badge-success' : 'badge-neutral'}">
                    ${c.status === 'REVIEWED' ? '✓ Đã xác nhận' : 'Chưa có'}
                </span>
            </td>
            <td>
                <span class="badge ${c.status === 'REVIEWED' ? 'badge-success' : (c.status === 'ANALYZED' ? 'badge-info' : 'badge-warning')}">
                     ${c.status === 'REVIEWED' ? '✓ Đã xác nhận mask' : (c.status === 'ANALYZED' ? '⚡ Đã chạy AI' : '⏳ Chờ phân tích')}
                </span>
            </td>
            <td>
                <button class="btn btn-sm btn-action-cell" onclick="openCaseDetailModal('${c.id}')">
                    👁️ Mở ca
                </button>
            </td>
        </tr>
    `}).join('');
}

async function openCaseDetailModal(studyId) {
            try {
                const resp = await fetch(`${API_BASE}/api/cases/${studyId}`);
                if (!resp.ok) throw new Error("Không thể tải chi tiết ca khám");
                const data = await resp.json();
                activeModalCase = data;

                document.getElementById('modalCaseTitle').innerText = `Hồ Sơ Ca Khám: ${data.study_code || data.study_id.substring(0, 8)}`;
                document.getElementById('modalCaseSubtitle').innerText = `Bệnh nhân: ${data.patient_id} | Ngày: ${data.study_date} | Trạng thái: ${data.status}`;

                const firstImg = data.images && data.images[0] ? data.images[0] : null;
                const review = firstImg ? firstImg.review : null;
                const pred = firstImg ? firstImg.prediction : null;

                const content = document.getElementById('modalCaseContent');
                content.innerHTML = `
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; background: var(--vm-bg-alt); padding: 16px; border-radius: var(--radius-md); font-size: 13.5px;">
                        <div><strong>Kỹ thuật:</strong> ${data.probe_type}</div>
                        <div><strong>Chỉ định:</strong> ${data.clinical_indication}</div>
                         <div><strong>Mask AI:</strong> ${pred ? 'Đã tạo' : 'Chưa có'}</div>
                         <div><strong>Mask cuối:</strong> ${review ? 'Đã rà soát' : 'Chưa xác nhận'}</div>
                    </div>
                    <div style="font-size: 13px; color: var(--vm-text-dark); background: var(--vm-card-white); border: 1px solid var(--vm-border); padding: 14px; border-radius: var(--radius-md);">
                         <strong>Ghi chú rà soát:</strong> ${review && review.clinical_notes ? review.clinical_notes : 'Chưa có ghi chú'}
                     </div>
                `;

                document.getElementById('caseDetailModal').classList.add('active');
            } catch (err) {
                showToast("Lỗi tải ca: " + err.message, false);
            }
        }

function closeCaseDetailModal() {
            document.getElementById('caseDetailModal').classList.remove('active');
            activeModalCase = null;
        }

async function handleDeleteCurrentCase() {
            if (!activeModalCase) return;
            if (!confirm(`Bạn có chắc chắn muốn xóa ca khám ${activeModalCase.study_code}?`)) return;

            try {
                const resp = await fetch(`${API_BASE}/api/cases/${activeModalCase.study_id}`, { method: 'DELETE' });
                if (!resp.ok) throw new Error("Lỗi khi xóa");
                showToast("✓ Đã xóa ca khám thành công!");
                closeCaseDetailModal();
                loadDashboardCases();
                loadHistoryTable();
            } catch (err) {
                showToast("Lỗi xóa: " + err.message, false);
            }
        }

function openCaseInViewer() {
    if (!activeModalCase) return;
    const caseData = activeModalCase;
    closeCaseDetailModal();

    const firstImg = caseData.images && caseData.images[0] ? caseData.images[0] : null;
    if (!firstImg) {
        showToast("Ca khám chưa có hình ảnh siêu âm được gắn.", false);
        return;
    }

    if (typeof currentCase === 'undefined' || !currentCase) {
        window.currentCase = {};
    }

    currentCase.patient_id = caseData.patient_id;
    currentCase.patient_name = caseData.patient_name || caseData.patient_id;
    currentCase.study_id = caseData.study_id || caseData.id;
    currentCase.study_code = caseData.study_code;
    currentCase.study_date = caseData.study_date;
    currentCase.clinical_indication = caseData.clinical_indication;
    currentCase.probe_type = caseData.probe_type;
    currentCase.image_id = firstImg.id;
    currentCase.doctor_action = firstImg.review ? firstImg.review.doctor_action : "ACCEPTED_RAW";

    if (firstImg.prediction) {
        const pred = firstImg.prediction;
        const review = firstImg.review;
        const activeMaskRle = (review && review.verified_mask_rle) ? review.verified_mask_rle : pred.rle_mask;
        window.currentPrediction = {
            image_id: firstImg.id,
            prediction_id: pred.prediction_id,
            measurements: pred.measurements,
            rle_mask: activeMaskRle,
            confidence_score: pred.confidence_score,
            overlay_base64: pred.overlay_base64,
            original_image_base64: firstImg.original_image_base64 || pred.original_image_base64,
            provenance: pred.provenance,
            uncertainty: pred.uncertainty,
            quality_gate: pred.quality_gate
        };
        initResultsWorkspace(currentPrediction);
        navigateTo('results');
        showToast("✓ Đã nạp ca khám lên bàn làm việc Viewer!");
    } else {
        navigateTo('upload');
        showToast("Ảnh chưa chạy mô hình U-Net, chuyển đến bước tải ảnh.");
    }
}

function downloadModalCaseReport() {
    openReportFromCaseDetail();
}
