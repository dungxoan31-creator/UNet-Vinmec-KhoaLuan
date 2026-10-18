/** Hash routing and common accessible UI for the research workflow. */
const API_BASE_URL = window.location.origin;
const API_BASE = API_BASE_URL;
const $ = id => document.getElementById(id);
let activeRoute = 'home';
let toastTimer;
const screens = {home:'screenDashboard',new_case:'screenUpload',cases:'screenHistory',results:'screenResults',evaluation:'screenEvaluation',admin:'screenAdmin'};
const routeAliases = {dashboard:'home',upload:'new_case',create_case:'new_case',dual_upload:'new_case',history:'cases',review:'results'};
function navigateTo(route, options={}) {
    route = routeAliases[route] || route;
    if (!screens[route]) route = 'home';
    if (route === 'results' && !currentPrediction) route = 'new_case';
    if (route !== 'home' && (!currentUser || !sessionStorage.getItem('ovarian_ai_access_token'))) {
        openLogin(route);
        route = 'home';
    }
    if (route === 'admin' && currentUser?.role !== 'ADMIN') route = 'home';
    if (currentCase.saving || currentCase.processing) {
        if (route !== activeRoute) {
            showToast('Đang xử lý. Vui lòng chờ thao tác hoàn tất.');
            history.replaceState(null, '', '#'+activeRoute);
            return;
        }
    }
    if (route === 'new_case' && activeRoute !== route && currentCase.study_id && !options.reuseCase) {
        if (!canReplaceCase()) {
            history.replaceState(null, '', '#'+activeRoute);
            return;
        }
        resetSingleCase();
    }
    const routeChanged = activeRoute !== route;
    if (routeChanged && route !== 'cases') clearTimeout(caseFilterTimer);
    activeRoute = route;
    Object.entries(screens).forEach(([key,id]) => {
        $(id).hidden = key !== route;
        $(id).classList.toggle('active', key === route);
    });
    document.querySelectorAll('[data-route]').forEach(link => {
        if (link.dataset.route === route || (route === 'results' && link.dataset.route === 'cases')) link.setAttribute('aria-current','page');
        else link.removeAttribute('aria-current');
    });
    if (location.hash !== '#'+route) history.pushState(null, '', '#'+route);
    if (route === 'cases') loadAllCases();
    if (route === 'evaluation') loadEvaluation();
    if (route === 'admin') loadAdminWorkspace();
    if (route === 'results') {
        syncReviewUI();
        if (!window.matchMedia('(min-width:1201px)').matches) $('reviewPanel').open = false;
    }
    if (routeChanged) window.scrollTo(0,0);
    document.title = (route === 'results' ? (currentCase.study_code || 'Case') : ({home:'Overview',new_case:'New Case',cases:'Cases',evaluation:'Evaluation',admin:'Admin'})[route])+' · Ovarian Segmentation';
}
function showToast(message, success=true) {
    clearTimeout(toastTimer);
    $('toast').textContent = message;
    $('toast').hidden = false;
    $('toast').style.background = success ? '#20435d' : '#8e3030';
    toastTimer = setTimeout(()=>$('toast').hidden=true, 5000);
}
function showError(id, message) { $(id).textContent = message || ''; $(id).hidden = !message; }
function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
}
function finiteMetric(value) { return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(3) : 'Chưa có'; }
async function apiJson(path, options={}) {
    const response = await authenticatedFetch(API_BASE+path, options);
    if (!response.ok) {
        // Deliberately don't display backend traces or arbitrary diagnostic detail.
        const messages = {401:'Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.',403:'Tài khoản chưa có quyền thực hiện thao tác này.',404:'Không tìm thấy dữ liệu. Hãy tải lại danh sách hoặc chọn ca khác.',409:'Ảnh đã có trong ca. Hãy mở lại ca hoặc tạo ca mới.',413:'Tệp vượt quá 20 MB. Hãy chọn ảnh nhỏ hơn.',422:'Ảnh hoặc mask không hợp lệ. Kiểm tra tệp siêu âm, vùng mask và thử lại.',503:'Mô hình hoặc dịch vụ chưa sẵn sàng. Hãy thử lại sau.'};
        throw new Error(messages[response.status] || 'Không thể hoàn tất yêu cầu. Hãy thử lại.');
    }
    return response.json();
}
function setupKeyboardShortcuts() {
    window.addEventListener('keydown', e => {
        if (activeRoute !== 'results' || document.querySelector('dialog[open]') || currentCase.saving || !currentCase.maskReady) return;
        if (e.code === 'Space' && activeRoute === 'results' && !e.target.closest('input,textarea,select,[contenteditable=true]')) {
            e.preventDefault();
            if (!isSpacePressed) {
                isSpacePressed = true;
                if (canvas && !isPanning) canvas.style.cursor = 'grab';
            }
            return;
        }
        if (e.target.closest('input,textarea,select,[contenteditable=true]')) return;
        const key = e.key.toLowerCase();
        if ((e.ctrlKey || e.metaKey) && key==='z') { e.preventDefault(); e.shiftKey ? redoCanvas() : undoCanvas(); }
        else if ((e.ctrlKey || e.metaKey) && key==='y') { e.preventDefault(); redoCanvas(); }
        else if (!e.ctrlKey && !e.metaKey && !e.altKey) {
            if (key==='b') setCanvasTool('brush');
            else if (key==='e') setCanvasTool('eraser');
            else if (key==='h') setCanvasTool('pan');
            else if (key==='[') { e.preventDefault(); setBrushSize(brushSize-2); }
            else if (key===']') { e.preventDefault(); setBrushSize(brushSize+2); }
            else if (key==='1') setViewMode('original');
            else if (key==='2') setViewMode('mask');
            else if (key==='3') setViewMode('overlay');
            else if (key==='+' || key==='=') zoomInCanvas();
            else if (key==='-') zoomOutCanvas();
            else if (key==='0') resetZoomCanvas();
            else if (key==='?' || (key==='/' && e.shiftKey)) openShortcutModal();
            else if (e.target === $('canvasContainer') && key.startsWith('arrow')) {
                e.preventDefault();
                if (key==='arrowleft') panOffsetX-=20;
                if (key==='arrowright') panOffsetX+=20;
                if (key==='arrowup') panOffsetY-=20;
                if (key==='arrowdown') panOffsetY+=20;
                applyCanvasZoom();
            }
        }
    });
    window.addEventListener('keyup', e => {
        if (e.code === 'Space') {
            isSpacePressed = false;
            if (canvas && !isPanning) canvas.style.cursor = currentTool === 'pan' ? 'grab' : 'none';
        }
    });
    window.addEventListener('hashchange',()=>navigateTo(location.hash.slice(1)));
    window.addEventListener('beforeunload', e => {
        if (currentCase.dirty || currentCase.saving || currentCase.processing) { e.preventDefault(); e.returnValue=''; }
    });
}
async function toggleViewerFullscreen() {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await $('imageViewer').requestFullscreen(); }
    catch { showToast('Trình duyệt chưa hỗ trợ toàn màn hình.',false); }
}
