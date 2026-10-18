/** Existing bearer-token authentication, without hospital role switching. */
let pendingRoute = 'home';
async function authenticatedFetch(url, options={}) {
    const headers = new Headers(options.headers);
    const token = sessionStorage.getItem('ovarian_ai_access_token');
    if (token) headers.set('Authorization','Bearer '+token);
    const response = await fetch(url,{...options,headers});
    if (response.status===401 && token) {
        sessionStorage.removeItem('ovarian_ai_access_token');
        currentUser = null;
        updateHeaderUserUI();
        openLogin(activeRoute);
    }
    return response;
}
function openLogin(route=activeRoute) {
    pendingRoute = route;
    showError('loginError','');
    $('loginPassword').type='password';
    $('loginPasswordToggle').textContent='Hiện';
    $('loginPasswordToggle').setAttribute('aria-label','Hiện mật khẩu');
    $('loginPasswordToggle').setAttribute('aria-pressed','false');
    $('logoutButton').hidden = !currentUser;
    if (!$('loginModal').open) $('loginModal').showModal();
    $('loginUsername').focus();
}
function toggleLoginPassword() {
    const show=$('loginPassword').type==='password';
    $('loginPassword').type=show?'text':'password';
    $('loginPasswordToggle').textContent=show?'Ẩn':'Hiện';
    $('loginPasswordToggle').setAttribute('aria-label',show?'Ẩn mật khẩu':'Hiện mật khẩu');
    $('loginPasswordToggle').setAttribute('aria-pressed',String(show));
}
async function loadCurrentUser() {
    if (!sessionStorage.getItem('ovarian_ai_access_token')) { currentUser=null; updateHeaderUserUI(); return false; }
    try {
        currentUser = await apiJson('/api/auth/current-user');
        currentRole = currentUser.role;
        updateHeaderUserUI();
        return true;
    } catch { currentUser=null; updateHeaderUserUI(); return false; }
}
function updateHeaderUserUI() {
    $('adminNav').hidden = currentUser?.role !== 'ADMIN';
    $('headerUserName').textContent = currentUser ? (currentUser.username || currentUser.full_name) : 'Đăng nhập';
    document.querySelector('.avatar').textContent = currentUser ? (currentUser.username || 'U').slice(0,1).toUpperCase() : 'U';
}
async function submitLogin(event) {
    event.preventDefault();
    $('loginSubmit').disabled=true;
    $('loginSubmit').textContent='Đang đăng nhập…';
    showError('loginError','');
    try {
        const response = await fetch(API_BASE+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('loginUsername').value.trim(),password:$('loginPassword').value})});
        if (!response.ok) throw new Error(response.status===401 ? 'Tên tài khoản hoặc mật khẩu không đúng.' : 'Dịch vụ đăng nhập chưa sẵn sàng. Hãy thử lại.');
        const data = await response.json();
        sessionStorage.setItem('ovarian_ai_access_token',data.access_token);
        currentUser=data.user; currentRole=data.user.role;
        $('loginPassword').value='';
        $('loginModal').close();
        updateHeaderUserUI();
        navigateTo(pendingRoute);
    } catch (error) { showError('loginError', error.message || 'Không thể đăng nhập. Kiểm tra kết nối và thử lại.'); }
    finally { $('loginSubmit').disabled=false; $('loginSubmit').textContent='Đăng nhập'; }
}
function logout() {
    if (currentCase.processing || currentCase.saving) return showToast('Chờ thao tác hoàn tất trước khi đăng xuất.');
    if (currentCase.dirty && !window.confirm('Mask hoặc ghi chú chưa lưu. Đăng xuất và bỏ thay đổi?')) return;
    sessionStorage.removeItem('ovarian_ai_access_token'); currentUser=null;
    resetSingleCase();
    $('adminModels').replaceChildren(); $('adminLogsBody').replaceChildren();
    $('reportPreviewModal').close();
    caseRequest++; evaluationRequest++; sampleRequest++; comparisonRequest++;
    allCases=[]; $('casesTableBody').replaceChildren(); $('evaluationRows').replaceChildren(); $('evaluationSplits').replaceChildren(); $('comparisonGrid').replaceChildren();
    $('loginPassword').value=''; $('loginModal').close(); updateHeaderUserUI(); navigateTo('home');
}
