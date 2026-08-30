/**
 * MODULE: AUTH.JS
 */


async function loadCurrentUser() {
            try {
                const resp = await fetch(`${API_BASE}/api/auth/current-user`);
                if (resp.ok) {
                    const u = await resp.json();
                    currentUser = u;
                    currentRole = u.role;
                    updateHeaderUserUI();
                }
            } catch (err) {
                console.error("Auth profile error:", err);
            }
        }

function applyRoleRBAC() {
    const dashNavBtn = document.getElementById('navDashboard');
    const dashDrawerBtn = document.getElementById('drawerNavDashboard');
    const adminNavBtn = document.getElementById('navAdminPortal');
    const adminDrawerBtn = document.getElementById('drawerNavAdmin');

    if (currentRole === 'ADMIN') {
        if (dashNavBtn) dashNavBtn.style.display = 'inline-flex';
        if (dashDrawerBtn) dashDrawerBtn.style.display = 'flex';
        if (adminNavBtn) adminNavBtn.style.display = 'inline-flex';
        if (adminDrawerBtn) adminDrawerBtn.style.display = 'flex';
    } else {
        // DOCTOR role: only allowed to view patients (Hồ Sơ Bệnh Án) & examine (Khám & Phân Tích)
        if (dashNavBtn) dashNavBtn.style.display = 'none';
        if (dashDrawerBtn) dashDrawerBtn.style.display = 'none';
        if (adminNavBtn) adminNavBtn.style.display = 'none';
        if (adminDrawerBtn) adminDrawerBtn.style.display = 'none';
    }
}

function handleBrandClick() {
    if (currentRole === 'ADMIN') {
        navigateTo('dashboard');
    } else {
        navigateTo('create_case');
    }
}

function updateHeaderUserUI() {
    const avatarEl = document.getElementById('headerUserAvatar');
    const nameEl = document.getElementById('headerUserName');
    const deptEl = document.getElementById('headerUserDept');
    const badgeEl = document.getElementById('headerRoleBadge');

    if (nameEl) nameEl.innerText = currentUser.full_name || (currentRole === 'ADMIN' ? 'BS.CKII Trần Quản Trị' : 'BS.CKI Nguyễn Văn A');
    if (deptEl) deptEl.innerText = currentUser.hospital || (currentRole === 'ADMIN' ? 'Ban Quản Trị AI Vinmec' : 'Vinmec Times City');

    if (badgeEl) {
        if (currentRole === 'ADMIN') {
            badgeEl.className = 'role-pill-badge role-pill-admin';
            badgeEl.innerText = 'ADMIN AI';
            if (avatarEl) {
                avatarEl.innerText = 'AD';
                avatarEl.style.background = 'linear-gradient(135deg, #7c3aed, #4f46e5)';
            }
        } else {
            badgeEl.className = 'role-pill-badge role-pill-doctor';
            badgeEl.innerText = 'BÁC SĨ';
            if (avatarEl) {
                avatarEl.innerText = 'BS';
                avatarEl.style.background = 'linear-gradient(135deg, var(--vm-blue-start), var(--vm-blue-end))';
            }
        }
    }

    applyRoleRBAC();
}

async function switchRole(role, showNotification = true) {
            try {
                const resp = await fetch(`${API_BASE}/api/auth/switch-role`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ role: role })
                });

                if (resp.ok) {
                    const data = await resp.json();
                    if (data.user) {
                        currentUser = data.user;
                    }
                }
            } catch (e) {
                console.warn("Switch role local fallback:", e);
            }

            currentRole = role.toUpperCase();
            if (currentRole === 'ADMIN') {
                currentUser.full_name = "BS.CKII Trần Quản Trị";
                currentUser.role = "ADMIN";
                currentUser.department = "Ban Giám Đốc & Trung Tâm AI Y Tế";
                currentUser.hospital = "Vinmec Healthcare System";
                currentUser.avatar = "AD";
            } else {
                currentUser.full_name = "BS.CKI Nguyễn Văn A";
                currentUser.role = "DOCTOR";
                currentUser.department = "Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa";
                currentUser.hospital = "Vinmec Times City (Hà Nội)";
                currentUser.avatar = "BS";
            }

            updateHeaderUserUI();

            if (showNotification) {
                if (currentRole === 'ADMIN') {
                    showToast("🛡️ Đã chuyển sang phân hệ Quản Trị Viên (Admin Portal)");
                    navigateTo('dashboard');
                } else {
                    showToast("🩺 Đã chuyển sang phân hệ Bác Sĩ Lâm Sàng (Khám & Phân Tích)");
                    navigateTo('create_case');
                }
            }
        }

function openRoleSwitchModal() {
            const cardDoc = document.getElementById('cardRoleDoctor');
            const cardAdm = document.getElementById('cardRoleAdmin');
            if (cardDoc && cardAdm) {
                if (currentRole === 'ADMIN') {
                    cardAdm.style.border = '2px solid #7c3aed';
                    cardAdm.style.background = '#faf5ff';
                    cardDoc.style.border = '1px solid var(--vm-border)';
                    cardDoc.style.background = 'var(--vm-card-white)';
                } else {
                    cardDoc.style.border = '2px solid var(--vm-primary-blue)';
                    cardDoc.style.background = '#f0f9ff';
                    cardAdm.style.border = '1px solid var(--vm-border)';
                    cardAdm.style.background = 'var(--vm-card-white)';
                }
            }
            document.getElementById('roleSwitchModal').classList.add('active');
        }

function closeRoleSwitchModal() {
            document.getElementById('roleSwitchModal').classList.remove('active');
        }

function handleSelectRoleChoice(role) {
            closeRoleSwitchModal();
            switchRole(role, true);
        }
