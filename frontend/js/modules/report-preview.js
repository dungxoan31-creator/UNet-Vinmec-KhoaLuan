/** Persisted research reports. Classic-script public functions match the existing modules. */
const researchReportPreview = (() => {
    const MAX_IMAGE_BYTES = 20 * 1024 * 1024;
    const state = { ready: null, controller: null, request: 0, sourceUrl: null, overlayUrl: null, exporting: false, printing: false };
    const changedMessage = 'Ca, ảnh hoặc kết quả rà soát đã thay đổi. Hãy mở lại ca và bản xem trước.';

    function snapshot() {
        if (!currentCase?.confirmed || currentCase.dirty || currentCase.saving) {
            throw new Error('Hãy xác nhận và lưu mask cùng ghi chú trước khi xuất báo cáo hoặc overlay.');
        }
        if (!currentUser?.username || !currentCase.study_id || !currentCase.image_id ||
            !currentCase.review_id || !currentPrediction?.prediction_id || !currentCase.savedMask) {
            throw new Error('Thiếu bản rà soát đã lưu hoặc phiên đăng nhập. Hãy mở lại ca.');
        }
        return {
            studyId: currentCase.study_id, imageId: currentCase.image_id,
            reviewId: currentCase.review_id, predictionId: currentPrediction.prediction_id,
            account: currentUser.username, mask: JSON.stringify(currentCase.savedMask),
            notes: currentCase.savedNotes
        };
    }

    function assertCurrent(expected) {
        const actual = snapshot();
        if (Object.keys(expected).some(key => actual[key] !== expected[key])) throw new Error(changedMessage);
    }

    function sameRle(a, b) {
        return Boolean(a && b && Array.isArray(a.shape) && Array.isArray(b.shape) &&
            a.shape.length === b.shape.length && a.shape.every((value, i) => value === b.shape[i]) &&
            (a.first_val ?? 0) === (b.first_val ?? 0) && Array.isArray(a.counts) && Array.isArray(b.counts) &&
            a.counts.length === b.counts.length && a.counts.every((value, i) => value === b.counts[i]));
    }

    async function readSaved(expected, signal) {
        assertCurrent(expected);
        const study = await apiJson('/api/cases/' + encodeURIComponent(expected.studyId), { cache: 'no-store', signal });
        assertCurrent(expected);
        const image = study.images?.find(item => item.image_id === expected.imageId);
        const review = image?.review;
        if (study.study_id !== expected.studyId || !image || review?.review_id !== expected.reviewId ||
            review.prediction_id !== expected.predictionId || image.prediction?.prediction_id !== expected.predictionId ||
            !sameRle(review.verified_mask_rle, JSON.parse(expected.mask))) {
            throw new Error(changedMessage);
        }
        return { study, image, review };
    }

    async function assertSavedUnchanged(expected, saved, signal) {
        const latest = await readSaved(expected, signal);
        // Includes persisted notes, actor, timestamp and calibration metadata, not just IDs.
        if (JSON.stringify(latest) !== JSON.stringify(saved)) throw new Error(changedMessage);
    }

    function dimensionsValid(width, height) {
        if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1 ||
            width * height * 4 > MAX_IMAGE_BYTES) {
            throw new Error('Ảnh nguồn vượt giới hạn bộ nhớ giải mã 20 MB hoặc có kích thước không hợp lệ.');
        }
    }

    async function fetchPng(path, signal) {
        const response = await authenticatedFetch(API_BASE + path, { cache: 'no-store', signal });
        if (!response.ok) throw new Error('Không tải được ảnh nguồn hoặc mask đã lưu. Hãy mở lại ca và thử lại.');
        if (Number(response.headers.get('Content-Length')) > MAX_IMAGE_BYTES) {
            throw new Error('Ảnh PNG vượt giới hạn 20 MB.');
        }
        let blob;
        if (response.body?.getReader) {
            const reader = response.body.getReader(), chunks = [];
            let size = 0;
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    size += value.byteLength;
                    if (size > MAX_IMAGE_BYTES) {
                        await reader.cancel();
                        throw new Error('Ảnh PNG vượt giới hạn 20 MB.');
                    }
                    chunks.push(value);
                }
                blob = new Blob(chunks, { type: 'image/png' });
            } finally { reader.releaseLock(); }
        } else {
            blob = await response.blob();
        }
        if (!blob.size || blob.size > MAX_IMAGE_BYTES) throw new Error('Ảnh PNG rỗng hoặc vượt giới hạn 20 MB.');
        // Check PNG dimensions before decoding so compressed oversized images cannot allocate an unlimited raster.
        const header = new Uint8Array(await blob.slice(0, 33).arrayBuffer());
        const signature = [137, 80, 78, 71, 13, 10, 26, 10];
        if (header.length < 33 || !signature.every((value, i) => header[i] === value) ||
            String.fromCharCode(...header.slice(12, 16)) !== 'IHDR') {
            throw new Error('Dịch vụ chưa trả ảnh PNG nguồn hợp lệ.');
        }
        const view = new DataView(header.buffer), width = view.getUint32(16), height = view.getUint32(20);
        dimensionsValid(width, height);
        return { blob, width, height };
    }

    async function makeOverlay(expected, measurements, signal) {
        const path = '/api/images/' + encodeURIComponent(expected.imageId);
        const assets = await Promise.allSettled([
            fetchPng(path + '/source.png', signal), fetchPng(path + '/mask.png?kind=reviewed', signal)
        ]);
        const failure = assets.find(result => result.status === 'rejected');
        if (failure) throw failure.reason;
        const [source, mask] = assets.map(result => result.value);
        const dims = measurements?.source_dimensions;
        if (source.width !== mask.width || source.height !== mask.height ||
            (measurements && (measurements.coordinate_space !== 'decoded-source-image' || !Array.isArray(dims) ||
                dims.length !== 2 || dims[0] !== source.width || dims[1] !== source.height))) {
            throw new Error('Kích thước ảnh, mask hoặc phép đo không khớp hệ tọa độ ảnh nguồn.');
        }
        const urls = [], canvases = [], images = [];
        try {
            for (const asset of [source, mask]) {
                const url = URL.createObjectURL(asset.blob);
                if (!url) throw new Error('Không có ảnh nguồn để giải mã.');
                urls.push(url);
                const image = await loadViewerImage(url);
                images.push(image);
                if (image.naturalWidth !== asset.width || image.naturalHeight !== asset.height) {
                    throw new Error('Kích thước PNG giải mã không khớp ảnh nguồn.');
                }
            }
            assertCurrent(expected);
            const canvas = document.createElement('canvas'), tint = document.createElement('canvas');
            canvases.push(canvas, tint);
            for (const item of canvases) { item.width = source.width; item.height = source.height; }
            const context = canvas.getContext('2d'), tintContext = tint.getContext('2d', { willReadFrequently: true });
            if (!context || !tintContext) throw new Error('Trình duyệt không hỗ trợ canvas để xuất overlay.');
            tintContext.drawImage(images[1], 0, 0);
            const pixels = tintContext.getImageData(0, 0, mask.width, mask.height);
            for (let i = 0; i < pixels.data.length; i += 4) {
                const foreground = pixels.data[i] > 0 && pixels.data[i + 3] > 0;
                pixels.data[i] = 0;
                pixels.data[i + 1] = pixels.data[i + 2] = 255;
                pixels.data[i + 3] = foreground ? 255 : 0;
            }
            tintContext.putImageData(pixels, 0, 0);
            context.drawImage(images[0], 0, 0);
            context.globalAlpha = 0.4;
            context.drawImage(tint, 0, 0);
            context.globalAlpha = 1;
            const blob = await new Promise((resolve, reject) => canvas.toBlob(
                value => value ? resolve(value) : reject(new Error('Không thể tạo ảnh overlay PNG.')), 'image/png'));
            if (blob.size > MAX_IMAGE_BYTES) throw new Error('Overlay PNG vượt giới hạn 20 MB.');
            assertCurrent(expected);
            return { blob, sourceBlob: source.blob, width: source.width, height: source.height };
        } finally {
            urls.forEach(url => URL.revokeObjectURL(url));
            images.forEach(image => image.removeAttribute('src'));
            canvases.forEach(canvas => { canvas.width = canvas.height = 0; });
        }
    }

    function calibrated(data) {
        const spacing = Array.isArray(data.pixel_spacing_mm) ? data.pixel_spacing_mm : [data.pixel_spacing_mm];
        return data.calibrated === true && ['DICOM', 'MANUAL'].includes(data.calibration_source) &&
            spacing.length > 0 && spacing.every(value => typeof value === 'number' && Number.isFinite(value) && value > 0);
    }

    function metric(value, unit) {
        return typeof value === 'number' && Number.isFinite(value) && value >= 0
            ? value.toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + ' ' + unit : 'Chưa có dữ liệu';
    }

    function facility() {
        const select = $('reportFacility');
        return select?.value ? select.selectedOptions[0]?.textContent.trim() || 'Chưa khai báo' : 'Chưa khai báo';
    }

    function laterality(value) {
        const code = String(value || 'UNKNOWN').trim().toUpperCase();
        switch (code) {
            case 'R': case 'RIGHT': return 'Phải (' + code + ')';
            case 'L': case 'LEFT': return 'Trái (' + code + ')';
            case 'BOTH': return 'Hai bên (BOTH)';
            default: return 'Chưa xác định (' + (code || 'UNKNOWN') + ')';
        }
    }

    function render(saved, measurements, overlay) {
        const { study, image, review } = saved, physical = calibrated(measurements);
        const escaped = value => escapeHtml(value === null || value === undefined || value === '' ? 'Chưa có dữ liệu' : value);
        const notes = review.saved_notes ?? review.clinical_notes;
        const morphology = !review.lesion_type || /^Chưa đánh giá/i.test(review.lesion_type) ? 'Chưa đánh giá' : review.lesion_type;
        const row = (label, value) => '<div><dt>' + label + '</dt><dd>' + escaped(value) + '</dd></div>';
        const measurementCells = (data, areaPx, areaCm2) => '<td>' + metric(physical ? data.max_diameter_mm : data.max_diameter_px, physical ? 'mm' : 'px') +
            '</td><td>' + metric(physical ? data.ortho_diameter_mm : data.ortho_diameter_px, physical ? 'mm' : 'px') +
            '</td><td>' + metric(physical ? areaCm2 : areaPx, physical ? 'cm²' : 'px²') + '</td>';
        const lesions = Array.isArray(measurements.lesions) ? measurements.lesions : [];
        $('reportPreviewContent').innerHTML = '<article class="research-report" aria-label="Báo cáo nghiên cứu đã lưu">' +
            '<header class="research-report-header"><img src="/static/assets/brand/vinmec-logo.png?v=20261018-transparent-logo" alt="Vinmec" width="112" height="64">' +
            '<div><p class="research-report-kicker">Hỗ trợ phân đoạn siêu âm buồng trứng</p><h1>Báo cáo rà soát phân đoạn siêu âm</h1>' +
            '<p>Cơ sở được chọn (bối cảnh nhập): <span data-report-facility>' + escaped(facility()) + '</span></p></div></header>' +
            '<p class="research-report-notice">Hỗ trợ phân đoạn siêu âm - Không thay thế chẩn đoán y khoa</p>' +
            '<section><h2>Thông tin ca và bản rà soát</h2><dl class="research-report-meta">' +
            row('PID', study.patient_id) + row('Mã ca', study.study_code || study.study_id) +
            row('Ngày khảo sát', study.study_date) + row('Thời điểm tạo ca (máy chủ)', study.created_at) +
            row('Bên khảo sát của ca', laterality(study.ovary_side)) + row('Bên của ảnh đang báo cáo', laterality(image.laterality)) +
            row('Ảnh đang báo cáo', image.filename || image.image_id) + row('Tài khoản người rà soát', review.doctor_id) +
            row('Mã rà soát', review.review_id) + row('Mã dự đoán được rà soát', review.prediction_id) +
            row('Phiên bản mô hình trong bản ghi', image.prediction?.model_version || image.prediction?.provenance?.model_version) +
            '</dl></section><section class="research-report-image"><h2>Đối chiếu ảnh nguồn và mask đã lưu</h2><div class="research-report-image-pair"><figure>' +
            '<img data-report-source alt="Ảnh siêu âm nguồn đầy đủ, chưa phủ mask">' +
            '<figcaption>Original · Ảnh nguồn · ' + overlay.width + ' × ' + overlay.height + ' px</figcaption></figure><figure>' +
            '<img data-report-overlay alt="Ảnh siêu âm nguồn với mask đã xác nhận phủ cyan 40%">' +
            '<figcaption>Confirmed Overlay · ' + overlay.width + ' × ' + overlay.height + ' px · Cyan 40%</figcaption></figure></div>' +
            '<p class="research-report-image-space">Cả hai ảnh sử dụng đầy đủ hệ tọa độ ảnh nguồn.</p></section>' +
            '<section><h2>Phép đo từ mask đã rà soát</h2>' +
            '<p class="research-report-calibration">' + (physical ? 'Đã hiệu chuẩn · Nguồn: ' + escaped(measurements.calibration_source) +
                ' · Spacing: ' + escaped([measurements.pixel_spacing_mm].flat().join(' × ')) + ' mm/px' :
                'Chưa có hiệu chuẩn vật lý hợp lệ. Phép đo chỉ hiển thị px/px² trong hệ tọa độ ảnh nguồn.') + '</p>' +
            '<div class="research-report-table-wrap"><table><thead><tr><th scope="col">Vùng mask</th><th scope="col">Đường kính lớn nhất</th>' +
            '<th scope="col">Đường kính vuông góc</th><th scope="col">Diện tích</th></tr></thead><tbody>' +
            '<tr><th scope="row">Tổng hợp</th>' + measurementCells(measurements, measurements.total_area_px, measurements.total_area_cm2) + '</tr>' +
            lesions.filter(item => item && typeof item === 'object').map((item, index) => '<tr><th scope="row">Vùng ' + escaped(item.lesion_id ?? index + 1) + '</th>' +
                measurementCells(item, item.area_px, item.area_cm2) + '</tr>').join('') + '</tbody></table></div></section>' +
            '<section><h2>Đánh giá hình thái do người rà soát nhập</h2><p class="research-report-notes">' + escaped(morphology) + '</p></section>' +
            '<section><h2>Ghi chú đã lưu</h2><p class="research-report-notes">' + escapeHtml(notes || 'Chưa có ghi chú đã lưu.') + '</p></section>' +
            '<section><h2>Chỉ định khảo sát đã lưu</h2><p class="research-report-notes">' + escaped(study.clinical_indication) + '</p></section>' +
            '<footer class="research-report-footer"><p>Tài khoản ghi nhận: <strong>' + escaped(review.doctor_id) + '</strong>' +
            ' · Thời điểm lưu (máy chủ): ' + escaped(review.reviewed_at || review.created_at) + '</p><p>Chưa có chữ ký số xác thực</p>' +
            '<p>Báo cáo phân đoạn siêu âm hỗ trợ hội chẩn. Kết quả cần được bác sĩ xác nhận, không thay thế chẩn đoán chuyên khoa độc lập.</p></footer></article>';
        $('reportPreviewContent').querySelector('[data-report-source]').src = state.sourceUrl;
        $('reportPreviewContent').querySelector('[data-report-overlay]').src = state.overlayUrl;
    }

    function reset() {
        state.request++;
        state.controller?.abort();
        state.controller = null;
        state.ready = null;
        if ($('reportPrintBtn')) $('reportPrintBtn').disabled = true;
        if ($('reportPreviewContent')) {
            $('reportPreviewContent').replaceChildren();
            $('reportPreviewContent').setAttribute('aria-busy', 'false');
        }
        if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
        if (state.overlayUrl) URL.revokeObjectURL(state.overlayUrl);
        state.sourceUrl = state.overlayUrl = null;
    }

    function wireDialog() {
        const dialog = $('reportPreviewModal');
        if (!dialog || dialog.dataset.reportWired) return;
        dialog.dataset.reportWired = 'true';
        // Native close is queued: an earlier close must not erase a newly reopened preview.
        dialog.addEventListener('close', () => { if (!dialog.open) reset(); });
        dialog.addEventListener('cancel', reset);
        $('reportFacility')?.addEventListener('change', () => {
            $('reportPreviewContent').querySelectorAll('[data-report-facility]').forEach(node => { node.textContent = facility(); });
        });
    }

    async function open() {
        if (state.printing || state.exporting) return;
        wireDialog();
        reset();
        const request = state.request, dialog = $('reportPreviewModal'), content = $('reportPreviewContent');
        if (!dialog || !content || !$('reportPrintBtn') || !$('reportPreviewError')) {
            showToast('Thiếu thành phần bản xem trước báo cáo.', false);
            return;
        }
        showError('reportPreviewError', '');
        if (!dialog.open) dialog.showModal();
        content.textContent = 'Đang tải ảnh nguồn và bản rà soát đã lưu…';
        content.setAttribute('aria-busy', 'true');
        const controller = new AbortController();
        state.controller = controller;
        try {
            const expected = snapshot(), saved = await readSaved(expected, controller.signal);
            const measurements = await apiJson('/api/images/' + encodeURIComponent(expected.imageId) + '/measurements', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
                body: JSON.stringify({ rle_mask: saved.review.verified_mask_rle })
            });
            const overlay = await makeOverlay(expected, measurements, controller.signal);
            await assertSavedUnchanged(expected, saved, controller.signal);
            if (request !== state.request || !dialog.open) return;
            state.sourceUrl = URL.createObjectURL(overlay.sourceBlob);
            state.overlayUrl = URL.createObjectURL(overlay.blob);
            render(saved, measurements, overlay);
            // Printing starts only after the report images have finished decoding.
            const images = [...content.querySelectorAll('img')];
            await Promise.all(images.map(image => image.decode()));
            if (request !== state.request || !dialog.open) return;
            assertCurrent(expected);
            state.ready = { expected, saved };
            $('reportPrintBtn').disabled = false;
        } catch (error) {
            if (request === state.request && error.name !== 'AbortError') {
                reset();
                showError('reportPreviewError', error.message || 'Không thể tạo bản xem trước. Dữ liệu ca vẫn được giữ.');
            }
        } finally {
            if (request === state.request) {
                state.controller = null;
                content.setAttribute('aria-busy', 'false');
            }
        }
    }

    function finishPrint() {
        document.getElementById('researchReportPrintRoot')?.remove();
        document.body.classList.remove('research-report-printing');
        state.printing = false;
    }

    function preparePrint() {
        // A normal-flow clone avoids native dialog's fixed top-layer pagination/clipping.
        finishPrint();
        if (!$('reportPreviewModal')?.open) return;
        const root = document.createElement('div');
        root.id = 'researchReportPrintRoot';
        try {
            if (!state.ready || $('reportPrintBtn').disabled) throw new Error(changedMessage);
            assertCurrent(state.ready.expected);
            $('reportPreviewContent').querySelectorAll('[data-report-facility]').forEach(node => { node.textContent = facility(); });
            root.append($('reportPreviewContent').firstElementChild.cloneNode(true));
        } catch {
            // Ctrl+P during loading/error must never print stale report or the clinical workspace.
            root.textContent = 'Bản xem trước chưa sẵn sàng. Hãy xác nhận, lưu và mở lại báo cáo.';
        }
        document.body.append(root);
        document.body.classList.add('research-report-printing');
        state.printing = true;
    }

    async function print() {
        if (!state.ready || state.printing || state.exporting || $('reportPrintBtn')?.disabled || !$('reportPreviewModal')?.open) return;
        const ready = state.ready;
        $('reportPrintBtn').disabled = true;
        try {
            await assertSavedUnchanged(ready.expected, ready.saved);
            if (state.ready !== ready || !$('reportPreviewModal').open) return;
            $('reportPrintBtn').disabled = false;
            preparePrint();
            window.print();
        } catch (error) {
            finishPrint();
            reset();
            showError('reportPreviewError', error.message || 'Không thể in báo cáo. Hãy thử lại.');
        }
    }

    async function exportOverlay() {
        if (state.exporting || state.controller || state.printing) return;
        state.exporting = true;
        try {
            const expected = snapshot(), saved = await readSaved(expected);
            const overlay = await makeOverlay(expected);
            await assertSavedUnchanged(expected, saved);
            const url = URL.createObjectURL(overlay.blob), link = document.createElement('a');
            try {
                link.href = url;
                const caseName = String(saved.study.study_code || saved.study.study_id).replace(/[<>:"/\\|?*\x00-\x1f]/g, '_');
                link.download = caseName + '-' + expected.imageId + '-confirmed-overlay.png';
                document.body.append(link);
                link.click();
            } finally {
                link.remove();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
            }
            showToast('Đã xuất overlay từ ảnh nguồn và mask đã xác nhận.');
        } catch (error) {
            showToast(error.message || 'Không thể xuất overlay. Dữ liệu ca vẫn được giữ.', false);
        } finally { state.exporting = false; }
    }

    window.addEventListener('beforeprint', preparePrint);
    window.addEventListener('afterprint', finishPrint);
    window.addEventListener('pagehide', () => { finishPrint(); reset(); });
    return { open, close: () => { if (state.printing) return; reset(); $('reportPreviewModal')?.close(); }, print, exportOverlay };
})();

async function openReportPreview() { return researchReportPreview.open(); }
function closeReportPreview() { researchReportPreview.close(); }
function printResearchReport() { return researchReportPreview.print(); }
async function exportConfirmedOverlay() { return researchReportPreview.exportOverlay(); }
