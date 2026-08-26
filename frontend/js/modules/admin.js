/**
 * MODULE: ADMIN.JS
 */


function switchAdminSubTab(tabName) {
            document.querySelectorAll('.admin-subnav-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.admin-tab-pane').forEach(p => p.style.display = 'none');

            const tabMap = {
                'overview': { btn: 'btnAdminTabOverview', pane: 'adminTabOverview' },
                'models': { btn: 'btnAdminTabModels', pane: 'adminTabModels' },
                'audit': { btn: 'btnAdminTabAudit', pane: 'adminTabAudit' },
                'doctors': { btn: 'btnAdminTabDoctors', pane: 'adminTabDoctors' },
                'dataset': { btn: 'btnAdminTabDataset', pane: 'adminTabDataset' }
            };

            const target = tabMap[tabName] || tabMap['overview'];
            const btnEl = document.getElementById(target.btn);
            const paneEl = document.getElementById(target.pane);

            if (btnEl) btnEl.classList.add('active');
            if (paneEl) paneEl.style.display = 'block';

            if (tabName === 'audit') loadAuditLogs();
            if (tabName === 'doctors') loadDoctorStats();
            if (tabName === 'overview') loadDashboardStats();
        }

async function loadAdminData() {
            showToast("Đang đồng bộ Telemetry và số liệu Real-time...", true);
            await loadDashboardStats();
            await loadAuditLogs();
            await loadDoctorStats();
        }

async function loadAuditLogs() {
            try {
                const resp = await fetch(`${API_BASE}/api/admin/audit-logs`);
                if (resp.ok) {
                    const logs = await resp.json();
                    const tbody = document.getElementById('adminAuditTableBody');
                    if (tbody) {
                        if (!logs || logs.length === 0) {
                            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--vm-text-muted); padding: 18px;">Chưa có nhật ký ký duyệt nào.</td></tr>`;
                            return;
                        }

                        tbody.innerHTML = logs.map(l => {
                            let actionBadge = `<span class="badge badge-success">✓ Đồng thuận AI (Accepted)</span>`;
                            if (l.action_type.includes("MODIFIED")) {
                                actionBadge = `<span class="badge badge-warning">✏️ Bác sĩ chỉnh sửa (Modified)</span>`;
                            } else if (l.action_type.includes("REJECTED")) {
                                actionBadge = `<span class="badge badge-danger">✕ Bác sĩ từ chối (Rejected)</span>`;
                            }

                            const timeSpent = (l.details && l.details.time_spent_s) ? `${l.details.time_spent_s}s` : '18s';
                            const diag = (l.details && l.details.lesion_type) ? ` (${l.details.lesion_type})` : '';

                            return `
                                <tr>
                                    <td><strong style="font-family: monospace; color: var(--vm-blue-end);">#${l.id}</strong></td>
                                    <td><strong>${l.actor_id}</strong></td>
                                    <td>${actionBadge}</td>
                                    <td><span style="font-family: monospace; font-weight: 600;">${l.entity_id.substring(0, 8)}...</span> ${diag}</td>
                                    <td><strong style="color: var(--vm-green);">${timeSpent}</strong></td>
                                    <td style="color: var(--vm-text-muted); font-size: 12px;">${l.timestamp}</td>
                                </tr>
                            `;
                        }).join('');
                    }
                }
            } catch (err) {
                console.error("Audit log error:", err);
            }
        }

async function loadDoctorStats() {
            try {
                const resp = await fetch(`${API_BASE}/api/admin/doctor-stats`);
                if (resp.ok) {
                    const doctors = await resp.json();
                    const container = document.getElementById('adminDoctorCardsContainer');
                    if (container) {
                        container.innerHTML = doctors.map(d => `
                            <div class="doctor-card-item">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <div style="display: flex; align-items: center; gap: 10px;">
                                        <div style="width: 38px; height: 38px; border-radius: 50%; background: linear-gradient(135deg, var(--vm-blue-start), var(--vm-blue-end)); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px;">
                                            BS
                                        </div>
                                        <div>
                                            <strong style="font-size: 14.5px; color: var(--vm-text-heading);">${d.doctor_name}</strong>
                                            <div style="font-size: 11.5px; color: var(--vm-text-muted);">${d.department}</div>
                                        </div>
                                    </div>
                                    <span class="badge badge-success">Online</span>
                                </div>

                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: var(--vm-bg-alt); padding: 10px; border-radius: var(--radius-sm); font-size: 12px; margin-top: 4px;">
                                    <div>Đã ký duyệt: <strong style="color: var(--vm-blue-end); font-size: 14px; font-family: monospace;">${d.signed_count} ca</strong></div>
                                    <div>Đồng thuận AI: <strong style="color: var(--vm-green); font-size: 14px; font-family: monospace;">${d.consensus_rate_pct}%</strong></div>
                                    <div>Chấp thuận gốc: <strong>${d.raw_accepted_count}</strong></div>
                                    <div>Đã chỉnh sửa: <strong>${d.modified_count}</strong></div>
                                </div>

                                <div style="display: flex; justify-content: space-between; font-size: 11.5px; color: var(--vm-text-muted); margin-top: 2px;">
                                    <span>Thời gian trung bình: <strong>${d.avg_review_seconds}s</strong></span>
                                    <span>Hoạt động: <strong>${d.last_active}</strong></span>
                                </div>
                            </div>
                        `).join('');
                    }
                }
            } catch (err) {
                console.error("Doctor stats error:", err);
            }
        }

async function exportDatasetJson() {
            try {
                showToast("Đang chuẩn bị tệp Ground Truth Dataset...", true);
                const resp = await fetch(`${API_BASE}/api/admin/export-dataset`);
                if (!resp.ok) throw new Error("Lỗi khi xuất dữ liệu");

                const blob = await resp.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Vinmec_Ovarian_AI_GroundTruth_Dataset.json`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                showToast("✓ Đã tải xuống tệp Vinmec_Ovarian_AI_GroundTruth_Dataset.json!");
            } catch (err) {
                showToast("Lỗi xuất dữ liệu: " + err.message, false);
            }
        }

async function openAdminModal() {
            navigateTo('admin_portal');
        }

function closeAdminModal() {
            const m = document.getElementById('adminModal');
            if (m) m.classList.remove('active');
        }
