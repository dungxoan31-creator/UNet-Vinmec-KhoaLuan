/**
 * MODULE: UPLOAD.JS
 */


function setupDragAndDrop() {
            const dropzone = document.getElementById('uploadDropzone');
            ['dragenter', 'dragover'].forEach(name => {
                dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
            });
            ['dragleave', 'drop'].forEach(name => {
                dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); });
            });
            dropzone.addEventListener('drop', (e) => {
                const files = e.dataTransfer.files;
                if (files && files.length > 0) {
                    processUploadedFile(files[0]);
                }
            });
        }

function handleFileSelected(e) {
            if (e.target.files && e.target.files.length > 0) {
                processUploadedFile(e.target.files[0]);
            }
        }

async function processUploadedFile(file) {
    const validExts = ['.png', '.jpg', '.jpeg', '.dcm'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!validExts.includes(ext)) {
        showToast("Định dạng file không hỗ trợ. Vui lòng chọn PNG, JPG, JPEG hoặc DICOM (.dcm).", false);
        return;
    }

    currentSelectedFile = file;
    const formData = new FormData();
    formData.append('file', file);
    if (typeof currentCase !== 'undefined' && currentCase && currentCase.study_id) {
        formData.append('study_id', currentCase.study_id);
    }
    const pid = (typeof currentCase !== 'undefined' && currentCase && currentCase.patient_id) ? currentCase.patient_id : 'BN-VINMEC';
    formData.append('anonymized_pid', pid);

    showToast("⚡ Tự động tải ảnh & thực thi AI phân tích...", true);

    try {
        const resp = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        if (!resp.ok) {
            let msg = "Lỗi khi tải file";
            try {
                const errJson = await resp.json();
                if (errJson.detail) msg = errJson.detail;
            } catch (e) {}
            throw new Error(msg);
        }
        const data = await resp.json();

        if (typeof currentCase === 'undefined' || !currentCase) {
            window.currentCase = {};
        }
        currentCase.image_id = data.image_id;
        currentCase.image_filename = data.filename;

        // Auto-navigate and execute full AI inference immediately
        navigateTo('ai_progress');
        executeInference();

    } catch (err) {
        showToast("Lỗi upload: " + err.message, false);
    }
}

function removeSelectedFile() {
            currentSelectedFile = null;
            document.getElementById('uploadPreviewList').style.display = 'none';
            if (document.getElementById('btnGoToIQA')) document.getElementById('btnGoToIQA').setAttribute('disabled', 'true');
            if (document.getElementById('btnFastTrack')) document.getElementById('btnFastTrack').setAttribute('disabled', 'true');
        }

async function startQualityCheck() {
            navigateTo('quality_check');
            try {
                const resp = await fetch(`${API_BASE}/api/validate-image?image_id=${currentCase.image_id}`, { method: 'POST' });
                if (!resp.ok) throw new Error("Lỗi khi kiểm tra chất lượng");
                const data = await resp.json();

                renderIQAChecklist(data);
            } catch (err) {
                showToast("Lỗi kiểm tra chất lượng ảnh", false);
            }
        }

function renderIQAChecklist(data) {
            const list = document.getElementById('iqaChecklistItems');
            list.innerHTML = data.details.map(item => `
                <div class="assessment-row ${item.status.toLowerCase()}">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 18px; color: ${item.status === 'PASS' ? 'var(--vm-accent-green)' : (item.status === 'WARN' ? 'var(--vm-accent-amber)' : 'var(--vm-accent-red)')};">
                            ${item.status === 'PASS' ? '✓' : (item.status === 'WARN' ? '⚠️' : '✕')}
                        </span>
                        <div>
                            <div style="font-weight: 700; font-size: 13.5px; color: var(--vm-text-heading);">${item.step}</div>
                            <div style="font-size: 12.5px; color: var(--vm-text-muted);">${item.desc}</div>
                        </div>
                    </div>
                    <span class="badge ${item.status === 'PASS' ? 'badge-success' : 'badge-warning'}">${item.status}</span>
                </div>
            `).join('');

            document.getElementById('iqaStatusTitle').innerText = data.status_text;
            document.getElementById('iqaStatusSubtitle').innerText = data.message;
        }

function startAIAnalysis() {
            navigateTo('ai_progress');
            document.getElementById('inferenceErrorBox').style.display = 'none';
            executeInference();
        }

async function executeInference() {
    const step3 = document.getElementById('infStep3');
    const step4 = document.getElementById('infStep4');
    const step5 = document.getElementById('infStep5');
    const errBox = document.getElementById('inferenceErrorBox');
    if (errBox) errBox.style.display = 'none';

    if (step3) step3.className = 'step-inf-item active';
    if (step4) step4.className = 'step-inf-item';
    if (step5) step5.className = 'step-inf-item';

    try {
        const resp = await fetch(`${API_BASE}/api/predict/${currentCase.image_id}`, { method: 'POST' });
        if (!resp.ok) {
            let errMsg = "Mô hình AI gặp lỗi khi phân tích";
            try {
                const errData = await resp.json();
                if (errData.detail) errMsg = errData.detail;
            } catch (e) {}
            throw new Error(errMsg);
        }
        const data = await resp.json();
        currentPrediction = data;

        if (step3) step3.className = 'step-inf-item done';
        if (step4) step4.className = 'step-inf-item done';
        if (step5) step5.className = 'step-inf-item done';

        initResultsWorkspace(data);
        navigateTo('results');
        showToast("✓ Phân tích hoàn tất — Bác sĩ vui lòng thẩm định kết quả!", true);

    } catch (err) {
        console.error("Inference execution notice:", err);
        if (step3) step3.className = 'step-inf-item fail';
        if (errBox) {
            errBox.innerHTML = `
                <div style="font-weight: 700; color: #b91c1c; font-size: 13.5px;">⚠️ Không thể hoàn thành phân tích:</div>
                <div style="color: #991b1b; font-size: 12.5px; margin-top: 4px;">${err.message}</div>
                <div style="display: flex; justify-content: center; gap: 10px; margin-top: 12px;">
                    <button type="button" class="btn btn-sm" onclick="navigateTo('upload')">← Chọn ảnh khác</button>
                    <button type="button" class="btn btn-primary btn-sm" onclick="executeInference()">Thử lại</button>
                </div>
            `;
            errBox.style.display = 'block';
        }
        showToast(err.message, false);
    }
}

function setupDualUpload() {
    document.getElementById('dualStudyDate').value = new Date().toISOString().slice(0, 10);
    for (const side of ['R', 'L']) {
        const input = document.getElementById(`dualFile${side}`);
        const target = document.querySelector(`.pacs-drop-target[data-side="${side}"]`);
        input.addEventListener('change', () => selectDualFile(side, input.files?.[0]));
        for (const eventName of ['dragenter', 'dragover']) {
            target.addEventListener(eventName, event => {
                event.preventDefault();
                target.classList.add('is-dragging');
            });
        }
        for (const eventName of ['dragleave', 'drop']) {
            target.addEventListener(eventName, event => {
                event.preventDefault();
                target.classList.remove('is-dragging');
            });
        }
        target.addEventListener('drop', event => selectDualFile(side, event.dataTransfer.files?.[0]));
    }
    document.getElementById('dualPatientId').addEventListener('input', updateDualUploadState);
    document.getElementById('dualSideConfirmed').addEventListener('change', updateDualUploadState);
    updateDualUploadState();
}

async function selectDualFile(side, file) {
    if (!file || dualCase.busy) return;
    const item = dualCase.sides[side];
    if (item.imageId) {
        showToast('Ảnh đã được lưu trong ca. Hãy tạo ca mới để thay ảnh.', false);
        return;
    }
    if (!/\.(png|jpe?g|dcm)$/i.test(file.name) || file.size < 64 || file.size > 20 * 1024 * 1024) {
        showToast('Chỉ nhận PNG/JPG/JPEG/DICOM từ 64 B đến 20 MB.', false);
        return;
    }
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    item.file = file;
    item.checksum = null;
    item.approved = false;
    document.getElementById('dualSideConfirmed').checked = false;
    const preview = document.getElementById(`dualPreview${side}`);
    const placeholder = document.getElementById(`dualPlaceholder${side}`);
    if (/\.(png|jpe?g)$/i.test(file.name)) {
        item.previewUrl = URL.createObjectURL(file);
        preview.src = item.previewUrl;
        preview.hidden = false;
        placeholder.hidden = true;
    } else {
        item.previewUrl = null;
        preview.hidden = true;
        placeholder.textContent = 'DICOM đã chọn · ảnh sẽ hiện sau khi backend giải mã';
        placeholder.hidden = false;
    }
    document.getElementById(`dualFileName${side}`).textContent = file.name;
    document.getElementById(`dualRemove${side}`).disabled = false;
    updateDualUploadState();
    try {
        if (!crypto.subtle) throw new Error('Cần HTTPS hoặc localhost để kiểm tra checksum.');
        const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
        if (item.file !== file) return;
        item.checksum = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    } catch (error) {
        showToast(error.message, false);
    }
    updateDualUploadState();
}

function removeDualFile(side) {
    const item = dualCase.sides[side];
    if (dualCase.busy || item.imageId) {
        showToast('Ảnh đã được lưu trong ca. Hãy tạo ca mới để thay ảnh.', false);
        return;
    }
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
    dualCase.sides[side] = newDualSide();
    document.getElementById('dualSideConfirmed').checked = false;
    document.getElementById(`dualFile${side}`).value = '';
    document.getElementById(`dualPreview${side}`).hidden = true;
    const placeholder = document.getElementById(`dualPlaceholder${side}`);
    placeholder.innerHTML = 'Kéo ảnh vào đây hoặc chọn tệp<br><small>PNG, JPG, JPEG, DICOM · tối đa 20 MB</small>';
    placeholder.hidden = false;
    document.getElementById(`dualFileName${side}`).textContent = 'Chưa chọn tệp';
    document.getElementById(`dualRemove${side}`).disabled = true;
    updateDualUploadState();
}

function updateDualUploadState() {
    const right = dualCase.sides.R;
    const left = dualCase.sides.L;
    const pid = document.getElementById('dualPatientId').value.trim();
    const sideConfirmed = document.getElementById('dualSideConfirmed').checked;
    const warning = document.getElementById('dualUploadWarning');
    const duplicate = right.checksum && right.checksum === left.checksum;
    const ready = Boolean(pid && right.file && left.file && right.checksum && left.checksum && sideConfirmed && !duplicate && !dualCase.busy);
    document.getElementById('dualRunBtn').disabled = !ready;
    warning.className = `pacs-inline-alert ${ready ? 'is-ready' : duplicate ? 'is-error' : ''}`;
    warning.textContent = dualCase.busy ? 'Đang tải ảnh và chạy suy diễn. Vui lòng chờ.'
        : duplicate ? 'Hai ảnh có SHA-256 giống nhau. Kiểm tra lại nhãn R/L và chọn ảnh khác.'
        : !pid ? 'Cần nhập mã hồ sơ ẩn danh.'
        : !right.file || !left.file ? 'Cần đủ hai ảnh R và L để chạy suy diễn.'
        : !right.checksum || !left.checksum ? 'Đang kiểm tra checksum hai ảnh.'
        : !sideConfirmed ? 'Cần đối chiếu và xác nhận ký hiệu R/L trên hai ảnh.'
        : 'Đã có hai ảnh khác nhau, sẵn sàng suy diễn.';
}

async function runDualInference() {
    if (document.getElementById('dualRunBtn').disabled || dualCase.busy) return;
    dualCase.busy = true;
    updateDualUploadState();
    try {
        if (!dualCase.studyId) {
            const pid = document.getElementById('dualPatientId').value.trim();
            const response = await fetch(`${API_BASE}/api/cases`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    patient_id: pid, patient_age: document.getElementById('dualPatientAge').value || null,
                    study_date: document.getElementById('dualStudyDate').value || null,
                    active_ovary_side: 'BOTH', clinical_notes: ''
                })
            });
            if (!response.ok) throw new Error('Không thể tạo ca khảo sát hai bên.');
            const study = await response.json();
            dualCase.studyId = study.study_id;
            dualCase.studyCode = study.study_code;
            dualCase.patientId = pid;
        }
        for (const side of ['R', 'L']) {
            const item = dualCase.sides[side];
            if (!item.imageId) {
                const form = new FormData();
                form.append('file', item.file);
                form.append('study_id', dualCase.studyId);
                form.append('laterality', side);
                form.append('anonymized_pid', dualCase.patientId);
                let response = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: form });
                if (response.status === 409) {
                    const detail = await fetch(`${API_BASE}/api/cases/${dualCase.studyId}`);
                    if (detail.ok) item.imageId = (await detail.json()).images.find(image => image.laterality === side)?.image_id || null;
                } else if (response.ok) {
                    item.imageId = (await response.json()).image_id;
                } else {
                    const message = (await response.json().catch(() => ({}))).detail;
                    throw new Error(message || `Không thể tải ảnh bên ${side}.`);
                }
                if (!item.imageId) throw new Error(`Không thể xác định ảnh bên ${side}.`);
            }
            if (!item.prediction) {
                const response = await fetch(`${API_BASE}/api/predict/${item.imageId}`, { method: 'POST' });
                if (!response.ok) {
                    const message = (await response.json().catch(() => ({}))).detail;
                    throw new Error(message || `Suy diễn bên ${side} không thành công.`);
                }
                item.prediction = await response.json();
                await prepareDualSide(side);
            }
        }
        document.getElementById('dualCaseMeta').textContent = `${dualCase.patientId} · ${dualCase.studyCode}`;
        renderDualComparison();
        navigateTo('dual_results');
        showToast('Đã tạo mask cho cả hai bên. Vui lòng rà soát từng ảnh.');
    } catch (error) {
        showToast(error.message, false);
    } finally {
        dualCase.busy = false;
        updateDualUploadState();
    }
}

function startNewDualCase() {
    if (dualCase.busy) {
        showToast('Đang tải ảnh và suy diễn. Vui lòng chờ hoàn tất.', false);
        return;
    }
    for (const side of ['R', 'L']) {
        if (dualCase.sides[side].previewUrl) URL.revokeObjectURL(dualCase.sides[side].previewUrl);
        dualCase.sides[side] = newDualSide();
        document.getElementById(`dualFile${side}`).value = '';
        document.getElementById(`dualPreview${side}`).hidden = true;
        const placeholder = document.getElementById(`dualPlaceholder${side}`);
        placeholder.innerHTML = 'Kéo ảnh vào đây hoặc chọn tệp<br><small>PNG, JPG, JPEG, DICOM · tối đa 20 MB</small>';
        placeholder.hidden = false;
        document.getElementById(`dualFileName${side}`).textContent = 'Chưa chọn tệp';
        document.getElementById(`dualRemove${side}`).disabled = true;
        document.getElementById(`dualNotes${side}`).value = '';
        document.getElementById(`dualStatus${side}`).textContent = 'Chưa có kết quả';
        const button = document.getElementById(`dualApprove${side}`);
        button.textContent = `Xác nhận & lưu ${side}`;
        button.classList.remove('is-approved');
        for (const name of ['Lesions', 'Diameters', 'Volume', 'Confidence']) {
            document.getElementById(`dual${name}${side}`).textContent = '—';
        }
        document.getElementById(`dualClinical${side}`).textContent = 'Chưa đánh giá';
    }
    dualCase.studyId = null;
    dualCase.studyCode = null;
    dualCase.patientId = null;
    dualCase.active = 'R';
    dualCase.mode = 'split';
    dualCase.sync = false;
    dualCase.showMask = true;
    dualCase.layerMode = 'overlay';
    dualCase.tool = 'brush';
    dualCase.brushSize = 16;
    dualCase.opacity = 0.45;
    dualCase.busy = false;
    document.getElementById('dualCaseMeta').textContent = 'Chưa có ca khảo sát';
    updateDualApprovalStatus();
    setDualViewMode('split');
    setDualLayerMode('overlay');
    setDualTool('brush');
    const syncButton = document.getElementById('dualSyncBtn');
    syncButton.classList.remove('is-active');
    syncButton.setAttribute('aria-pressed', 'false');
    document.getElementById('dualBrushSize').value = '16';
    document.getElementById('dualBrushSizeVal').textContent = '16 px';
    document.getElementById('dualOpacity').value = '45';
    document.getElementById('dualOpacityVal').textContent = '45%';
    for (const side of ['R', 'L']) {
        const canvas = document.getElementById(`dualCanvas${side}`);
        canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
        canvas.style.transform = '';
        document.getElementById(`dualZoom${side}`).textContent = '100%';
    }
    selectDualViewport('R');
    document.getElementById('dualPatientId').value = '';
    document.getElementById('dualPatientAge').value = '';
    document.getElementById('dualSideConfirmed').checked = false;
    document.getElementById('dualStudyDate').value = new Date().toISOString().slice(0, 10);
    updateDualUploadState();
    navigateTo('dual_upload');
}

async function openDualCase(studyId) {
    if (dualCase.busy) return;
    dualCase.busy = true;
    try {
        const response = await fetch(`${API_BASE}/api/cases/${studyId}`);
        if (!response.ok) throw new Error('Không thể tải ca khảo sát hai bên.');
        const study = await response.json();
        if (study.ovary_side !== 'BOTH') throw new Error('Ca này không thuộc quy trình hai bên.');
        const records = Object.fromEntries(study.images.filter(image => image.laterality).map(image => [image.laterality, image]));
        if (!records.R?.prediction || !records.L?.prediction) {
            throw new Error('Ca chưa có đủ hai dự đoán R/L để mở workstation.');
        }
        const originals = await Promise.all(['R', 'L'].map(async side => {
            const source = await fetch(`${API_BASE}/api/images/${records[side].image_id}/viewer-source`);
            if (!source.ok) throw new Error(`Không thể tải ảnh nguồn bên ${side}.`);
            return (await source.json()).original_image_base64;
        }));
        for (const side of ['R', 'L']) {
            if (dualCase.sides[side].previewUrl) URL.revokeObjectURL(dualCase.sides[side].previewUrl);
        }
        dualCase.studyId = study.study_id;
        dualCase.studyCode = study.study_code;
        dualCase.patientId = study.patient_id;
        dualCase.sides = { R: newDualSide(), L: newDualSide() };
        dualCase.active = 'R';
        dualCase.sync = false;
        document.getElementById('dualSyncBtn').classList.remove('is-active');
        document.getElementById('dualSyncBtn').setAttribute('aria-pressed', 'false');
        for (const [index, side] of ['R', 'L'].entries()) {
            const item = dualCase.sides[side];
            item.imageId = records[side].image_id;
            item.prediction = { ...records[side].prediction, original_image_base64: originals[index] };
            await prepareDualSide(side);
            const review = records[side].review;
            if (review) {
                item.mask = dualMaskFromRle(review.verified_mask_rle);
                item.undo = [item.mask.getContext('2d').getImageData(0, 0, 512, 512)];
                item.approved = true;
                item.reviewId = review.review_id;
                document.getElementById(`dualNotes${side}`).value = review.clinical_notes || '';
                document.getElementById(`dualStatus${side}`).textContent = 'Đã lưu rà soát';
                const button = document.getElementById(`dualApprove${side}`);
                button.textContent = `Đã lưu ${side} · lưu lại`;
                button.classList.add('is-approved');
                renderDualSide(side);
            } else {
                document.getElementById(`dualNotes${side}`).value = '';
                const button = document.getElementById(`dualApprove${side}`);
                button.textContent = `Xác nhận & lưu ${side}`;
                button.classList.remove('is-approved');
            }
        }
        document.getElementById('dualCaseMeta').textContent = `${study.patient_id} · ${study.study_code}`;
        setDualViewMode('split');
        setDualLayerMode('overlay');
        selectDualViewport('R');
        renderDualComparison();
        updateDualApprovalStatus();
        closeCaseDetailModal();
        navigateTo('dual_results');
    } catch (error) {
        showToast(error.message, false);
    } finally {
        dualCase.busy = false;
        updateDualUploadState();
    }
}
