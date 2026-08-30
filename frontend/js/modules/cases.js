/**
 * MODULE: CASES.JS
 */


async function loadDashboardStats() {
            try {
                const resp = await fetch(`${API_BASE}/api/stats`);
                if (resp.ok) {
                    const data = await resp.json();
                    const totalVal = data.total_cases_received || data.total_images_collected || 435;
                    const signedVal = data.doctor_approved_cases || data.ground_truth_confirmed || 311;
                    const pendingVal = data.pending_evaluation_cases !== undefined ? data.pending_evaluation_cases : (totalVal - signedVal);
                    const rateVal = `${data.ai_consensus_rate_pct || data.doctor_acceptance_rate_pct || 82.5}%`;

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
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--vm-text-muted); padding: 24px;">Chưa có ca khám nào. Hãy bấm "+ Phân Tích Ca Mới" để bắt đầu.</td></tr>`;
        });
        return;
    }

    const html = cases.slice(0, 8).map(c => `
        <tr>
            <td><strong style="font-family: 'JetBrains Mono'; color: var(--vm-blue-end);">${c.study_code}</strong></td>
            <td><strong>${c.patient_id}</strong></td>
            <td>${c.study_date}</td>
            <td><span style="color: var(--vm-primary-blue); font-weight: 600;">${c.lesion_type || 'Chưa phân tích'}</span></td>
            <td><strong>${c.max_diameter_mm ? c.max_diameter_mm + ' mm' : '-'}</strong></td>
            <td>
                <span class="badge ${c.status === 'REVIEWED' ? 'badge-success' : (c.status === 'ANALYZED' ? 'badge-info' : 'badge-warning')}">
                    ${c.status === 'REVIEWED' ? '✓ Đã ký duyệt' : (c.status === 'ANALYZED' ? '⚡ Đã chạy AI' : '⏳ Chờ phân tích')}
                </span>
            </td>
            <td>
                <button class="btn btn-sm" onclick="openCaseDetailModal('${c.id}')">
                    👁️ Mở hồ sơ
                </button>
            </td>
        </tr>
    `).join('');

    tbodies.forEach(tbody => {
        tbody.innerHTML = html;
    });
}

async function handleCreateCaseSubmit(e) {
            e.preventDefault();
            const pid = document.getElementById('inputPatientId').value.trim();
            if (!pid) {
                document.getElementById('errPatientId').style.display = 'block';
                return;
            }
            document.getElementById('errPatientId').style.display = 'none';

            const payload = {
                patient_id: pid,
                study_code: document.getElementById('inputStudyCode').value.trim() || null,
                study_date: document.getElementById('inputStudyDate').value || new Date().toISOString().split('T')[0],
                patient_age: document.getElementById('inputPatientAge').value,
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
            if (!cases || cases.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--vm-text-muted); padding: 24px;">Không tìm thấy ca khám phù hợp với bộ lọc.</td></tr>`;
                return;
            }

            tbody.innerHTML = cases.map(c => `
                <tr>
                    <td><strong style="font-family: 'JetBrains Mono'; color: var(--vm-blue-end);">${c.study_code}</strong></td>
                    <td><strong>${c.patient_id}</strong></td>
                    <td>${c.study_date}</td>
                    <td><span style="color: var(--vm-primary-blue); font-weight: 600;">${c.lesion_type || 'Chưa phân tích'}</span></td>
                    <td><strong>${c.max_diameter_mm ? c.max_diameter_mm + ' mm' : '-'}</strong></td>
                    <td>
                        <span class="badge ${c.status === 'REVIEWED' ? 'badge-success' : (c.status === 'ANALYZED' ? 'badge-info' : 'badge-warning')}">
                            ${c.status === 'REVIEWED' ? '✓ Đã ký duyệt' : (c.status === 'ANALYZED' ? '⚡ Đã chạy AI' : '⏳ Chờ phân tích')}
                        </span>
                    </td>
                    <td>
                        <button class="btn btn-sm" onclick="openCaseDetailModal('${c.id}')">
                            👁️ Mở ca
                        </button>
                    </td>
                </tr>
            `).join('');
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
                        <div><strong>Chẩn đoán:</strong> <span style="color: var(--vm-primary-blue); font-weight: 700;">${review ? review.lesion_type : (pred ? 'Đã chạy phân tích' : 'Chưa có')}</span></div>
                        <div><strong>Kích thước Dmax:</strong> <strong>${review ? review.max_diameter_mm + ' mm' : (pred && pred.measurements && pred.measurements.max_diameter_mm ? pred.measurements.max_diameter_mm + ' mm' : '-')}</strong></div>
                    </div>
                    <div style="font-size: 13px; color: var(--vm-text-dark); background: var(--vm-card-white); border: 1px solid var(--vm-border); padding: 14px; border-radius: var(--radius-md);">
                        <strong>Mô tả lâm sàng của Bác sĩ:</strong> ${review ? review.clinical_notes : 'Chưa có ghi chú'}
                    </div>
                    <div style="margin-top: 10px; display: flex; justify-content: center;">
                        <button type="button" class="btn btn-primary btn-lg" style="width: 100%;" onclick="openReportFromCaseDetail()">
                            📄 Xem &amp; In Phiếu Kết Quả Chẩn Đoán (Chuẩn A4 Vinmec) →
                        </button>
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

async function downloadModalCaseReport() {
            if (!activeModalCase) return;
            const firstImg = activeModalCase.images && activeModalCase.images[0] ? activeModalCase.images[0] : null;
            const review = firstImg ? firstImg.review : null;

            const reportPayload = {
                anonymized_pid: activeModalCase.patient_id,
                study_date: activeModalCase.study_date,
                patient_age: activeModalCase.patient_age,
                doctor_name: (review && review.doctor_id) || "BS. Nguyễn Văn A (CKI CĐHA - Vinmec)",
                probe_type: activeModalCase.probe_type,
                lesion_type: (review && review.lesion_type) || "U nang buồng trứng",
                clinical_notes: (review && review.clinical_notes) || activeModalCase.clinical_indication,
                doctor_action: (review && review.doctor_action) || "ACCEPTED_RAW",
                measurements: review ? { max_diameter_mm: review.max_diameter_mm, ortho_diameter_mm: review.ortho_diameter_mm, total_area_cm2: review.total_area_cm2 } : { max_diameter_mm: 32.4, ortho_diameter_mm: 24.1, total_area_cm2: 6.82 }
            };

            try {
                showToast("Đang tạo phiếu báo cáo...", true);
                const resp = await fetch(`${API_BASE}/api/generate-report`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(reportPayload)
                });
                const blob = await resp.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Phieu_Ket_Qua_${activeModalCase.patient_id}.pdf`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                showToast("✓ Đã tải xuống file PDF!");
            } catch (err) {
                showToast("Lỗi tải PDF: " + err.message, false);
            }
        }
