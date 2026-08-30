/**
 * MODULE: NAVIGATION.JS
 */


function navigateTo(screenName) {
    // RBAC Guard: Bác sĩ chỉ được dùng để khám bệnh (Khám & Phân Tích) và xem hồ sơ bệnh nhân (Hồ Sơ Bệnh Án)
    if ((screenName === 'admin_portal' || screenName === 'dashboard') && currentRole !== 'ADMIN') {
        showToast("⚠️ Phân quyền: Bác sĩ chỉ có quyền thực hiện Khám & Phân Tích và xem Hồ Sơ Bệnh Án.", false);
        navigateTo('create_case');
        return;
    }

    document.querySelectorAll('.screen-container').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item-btn').forEach(b => b.classList.remove('active'));

    if (screenName === 'dashboard') {
        document.getElementById('screenDashboard').classList.add('active');
        document.getElementById('navDashboard').classList.add('active');
        loadDashboardStats();
        loadDashboardCases();
        checkDraftOnLoad();
    } else if (screenName === 'create_case') {
        document.getElementById('screenCreateCase').classList.add('active');
        document.getElementById('navNewCase').classList.add('active');
        const studyDateInput = document.getElementById('inputStudyDate');
        if (studyDateInput && !studyDateInput.value) {
            studyDateInput.value = new Date().toISOString().split('T')[0];
        }
    } else if (screenName === 'upload') {
        document.getElementById('screenUpload').classList.add('active');
        const pidEl = document.getElementById('uploadCurrentPidText');
        if (pidEl) pidEl.innerText = (typeof currentCase !== 'undefined' && currentCase && currentCase.patient_id) ? currentCase.patient_id : 'BN-VINMEC';
    } else if (screenName === 'quality_check') {
        document.getElementById('screenQualityCheck').classList.add('active');
    } else if (screenName === 'ai_progress') {
        document.getElementById('screenAIProgress').classList.add('active');
    } else if (screenName === 'results') {
        document.getElementById('screenResults').classList.add('active');
    } else if (screenName === 'report_complete') {
        document.getElementById('screenReportComplete').classList.add('active');
    } else if (screenName === 'history') {
        document.getElementById('screenHistory').classList.add('active');
        document.getElementById('navHistory').classList.add('active');
        loadHistoryTable();
    } else if (screenName === 'admin_portal') {
        document.getElementById('screenAdminPortal').classList.add('active');
        const adminNavBtn = document.getElementById('navAdminPortal');
        if (adminNavBtn) adminNavBtn.classList.add('active');
        loadAdminData();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function executeQuickSearch() {
            const query = document.getElementById('quickSearchInput').value.trim();
            if (query) {
                navigateTo('history');
                document.getElementById('histSearchInput').value = query;
                filterHistory();
            }
        }

function showToast(msg, isSuccess = true) {
            const toast = document.getElementById('toastNotification');
            document.getElementById('toastMsg').innerText = msg;
            document.getElementById('toastIcon').innerText = isSuccess ? '✓' : '⚠️';
            toast.style.borderLeftColor = isSuccess ? 'var(--vm-green)' : 'var(--vm-accent-red)';
            toast.style.display = 'flex';
            setTimeout(() => { toast.style.display = 'none'; }, 3200);
        }

function toggleMobileDrawer() {
            const overlay = document.getElementById('mobileDrawerOverlay');
            if (overlay) overlay.classList.toggle('active');
        }

function closeMobileDrawer() {
            const overlay = document.getElementById('mobileDrawerOverlay');
            if (overlay) overlay.classList.remove('active');
        }

document.addEventListener('DOMContentLoaded', () => {
            const overlay = document.getElementById('mobileDrawerOverlay');
            if (overlay) {
                overlay.addEventListener('click', (e) => {
                    if (e.target === overlay) closeMobileDrawer();
                });
            }
        });

function setupKeyboardShortcuts() {
            window.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                if (e.code === 'Space') {
                    e.preventDefault();
                    toggleMaskOverlay();
                } else if (e.key === 'b' || e.key === 'B') {
                    setCanvasTool('brush');
                } else if (e.key === 'e' || e.key === 'E') {
                    setCanvasTool('eraser');
                } else if (e.key === '+' || e.key === '=') {
                    zoomInCanvas();
                } else if (e.key === '-' || e.key === '_') {
                    zoomOutCanvas();
                } else if (e.key === '0') {
                    resetZoomCanvas();
                } else if (e.ctrlKey && (e.key === 'z' || e.key === 'Z')) {
                    e.preventDefault();
                    undoCanvas();
                } else if (e.ctrlKey && (e.key === 'y' || e.key === 'Y')) {
                    e.preventDefault();
                    redoCanvas();
                }
            });
        }
