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
    const validExts = ['.png', '.jpg', '.jpeg'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!validExts.includes(ext)) {
        showToast("Định dạng file không hỗ trợ. Vui lòng chọn PNG hoặc JPG.", false);
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
