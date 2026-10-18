/** Admin research workspace. Classic-script exports match the existing frontend. */
(() => {
    let requestId = 0, owner = null, logs = null;
    let logMessage = 'Chưa tải nhật ký.';
    const unavailable = 'Chưa có dữ liệu';
    const isAdmin = () => !!currentUser && currentRole === 'ADMIN' && currentUser.role === 'ADMIN';
    const text = value => value == null || value === '' ? unavailable : String(value);

    function message(value) {
        const element = $('adminMessage');
        if (element) {
            element.setAttribute('role', 'status');
            element.setAttribute('aria-live', 'polite');
            element.textContent = value;
        }
    }

    function logNotice(value) {
        const body = $('adminLogsBody');
        if (!body) return;
        const row = document.createElement('tr'), cell = document.createElement('td');
        cell.colSpan = 4;
        cell.className = 'admin-empty';
        cell.textContent = value;
        row.append(cell);
        body.replaceChildren(row);
    }

    function actionOptions(actions = []) {
        const select = $('adminActionFilter');
        if (!select) return;
        const previous = select.value;
        select.replaceChildren();
        for (const action of ['ALL', ...actions.filter(action => action !== 'ALL')]) {
            const option = document.createElement('option');
            option.value = action;
            option.textContent = action === 'ALL' ? 'Tất cả thao tác' : action;
            select.append(option);
        }
        select.value = actions.includes(previous) ? previous : 'ALL';
    }

    function clearWorkspace() {
        requestId++;
        owner = null;
        logs = null;
        logMessage = 'Chỉ tài khoản ADMIN được truy cập dữ liệu quản trị.';
        $('adminModels')?.replaceChildren();
        $('adminLogsBody')?.replaceChildren();
        actionOptions();
        if ($('adminActorFilter')) $('adminActorFilter').value = '';
        if ($('adminLogCount')) $('adminLogCount').textContent = '0 nhật ký';
        $('screenAdmin')?.setAttribute('aria-busy', 'false');
        message(logMessage);
    }

    function fields(values) {
        return values.map(([label, value]) => '<div><dt>' + escapeHtml(label) +
            '</dt><dd>' + escapeHtml(text(value)) + '</dd></div>').join('');
    }

    function renderModels(data) {
        const container = $('adminModels');
        if (!container) return;
        const latency = data.mean_inference_latency_ms;
        const summary = '<dl class="admin-summary">' + fields([
            ['Mô hình chính', data.active_primary_model],
            ['Thiết bị thực thi', data.execution_device],
            ['Độ trễ TB từ bản ghi', typeof latency === 'number' && Number.isFinite(latency) ? latency.toFixed(1) + ' ms' : null],
            ['Số mẫu thời gian', data.latency_sample_count],
            ['Phạm vi thời gian', data.latency_scope === 'all_recorded_predictions' ? 'Các dự đoán đã lưu, mọi phiên bản' : null]
        ]) + '</dl>';
        // Current get_info() exposes neither checksum nor threshold. No inferred defaults.
        const models = data.registered_models.map(model =>
            '<article class="admin-model"><h3>' + escapeHtml(text(model.name)) + '</h3>' +
            '<dl>' + fields([
                ['Phiên bản', model.version],
                ['Kiến trúc', model.architecture],
                ['Trạng thái trọng số', typeof model.is_loaded === 'boolean' ?
                    (model.is_loaded ? 'Đã nạp' : 'Chưa nạp') : null],
                ['Checksum', model.checksum],
                ['Ngưỡng phân đoạn', model.threshold]
            ]) + '</dl></article>'
        ).join('');
        container.innerHTML = summary + '<div class="admin-model-list">' +
            (models || '<p class="admin-empty">Chưa có mô hình được đăng ký.</p>') + '</div>';
    }

    function filterAdminLogs() {
        if (!isAdmin()) { clearWorkspace(); return; }
        if (owner !== currentUser) { clearWorkspace(); message('Nhấn Refresh để tải dữ liệu quản trị.'); return; }
        if (logs === null) { logNotice(logMessage); return; }
        const actor = ($('adminActorFilter')?.value || '').trim().toLocaleLowerCase();
        const action = $('adminActionFilter')?.value || 'ALL';
        const visible = logs.filter(log =>
            String(log.actor_id ?? '').toLocaleLowerCase().includes(actor) &&
            (action === 'ALL' || log.action_type === action));
        if ($('adminLogCount')) $('adminLogCount').textContent =
            visible.length + ' / ' + logs.length + ' nhật ký (tối đa 50 mới nhất)';
        const body = $('adminLogsBody');
        if (!body) return;
        if (!visible.length) {
            logNotice(logs.length ? 'Không có nhật ký phù hợp với bộ lọc.' : 'Chưa có nhật ký.');
            return;
        }
        body.innerHTML = visible.map(log => '<tr><td>' + escapeHtml(text(log.timestamp)) +
            '</td><td>' + escapeHtml(text(log.actor_id)) + '</td><td>' +
            escapeHtml(text(log.action_type)) + '</td><td class="admin-log-details">' +
            escapeHtml(log.details == null ? unavailable : JSON.stringify(log.details, null, 2)) +
            '</td></tr>').join('');
    }

    async function loadAdminWorkspace() {
        if (!isAdmin()) { clearWorkspace(); return; }
        const request = ++requestId, user = currentUser;
        const changedUser = owner !== user;
        owner = user;
        logs = null;
        logMessage = 'Đang tải nhật ký…';
        $('adminModels')?.replaceChildren();
        if (changedUser) {
            actionOptions();
            if ($('adminActorFilter')) $('adminActorFilter').value = '';
        }
        if ($('adminLogCount')) $('adminLogCount').textContent = 'Đang tải…';
        $('screenAdmin')?.setAttribute('aria-busy', 'true');
        message('Đang tải mô hình và tối đa 50 nhật ký mới nhất…');
        logNotice(logMessage);

        const results = await Promise.allSettled([
            apiJson('/api/admin/models'),
            apiJson('/api/admin/audit-logs?limit=50')
        ]);
        if (request !== requestId) return;
        if (!isAdmin() || currentUser !== user) { clearWorkspace(); return; }

        const errors = [];
        try {
            if (results[0].status === 'rejected') throw results[0].reason;
            const data = results[0].value;
            if (!data || !Array.isArray(data.registered_models) ||
                data.registered_models.some(model => !model || typeof model !== 'object' || Array.isArray(model)))
                throw new Error('Dữ liệu mô hình không đúng cấu trúc API.');
            renderModels(data);
        } catch (error) {
            const notice = 'Không tải được mô hình: ' + (error?.message || 'Dịch vụ chưa sẵn sàng.');
            if ($('adminModels')) $('adminModels').textContent = notice;
            errors.push(notice);
        }
        try {
            if (results[1].status === 'rejected') throw results[1].reason;
            const data = results[1].value;
            if (!Array.isArray(data) || data.some(log => !log || typeof log !== 'object' || Array.isArray(log)))
                throw new Error('Dữ liệu nhật ký không đúng cấu trúc API.');
            logs = data.slice(0, 50);
            actionOptions([...new Set(logs.map(log => log.action_type).filter(action =>
                typeof action === 'string' && action.length))].sort());
        } catch (error) {
            logMessage = 'Không tải được nhật ký: ' + (error?.message || 'Dịch vụ chưa sẵn sàng.');
            if ($('adminLogCount')) $('adminLogCount').textContent = 'Nhật ký chưa có dữ liệu';
            actionOptions();
            errors.push(logMessage);
        }
        filterAdminLogs();
        $('screenAdmin')?.setAttribute('aria-busy', 'false');
        message(errors.length ? errors.join(' ') + ' Nhấn Refresh để thử lại.' :
            'Dữ liệu từ API quản trị; chỉ lọc tối đa 50 nhật ký mới nhất. Hỗ trợ phân đoạn siêu âm, không dùng để chẩn đoán.');
    }

    window.loadAdminWorkspace = loadAdminWorkspace;
    window.filterAdminLogs = filterAdminLogs;
})();
