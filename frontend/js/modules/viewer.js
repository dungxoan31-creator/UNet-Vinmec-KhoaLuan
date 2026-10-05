/**
 * MODULE: VIEWER.JS
 */

const MAX_HISTORY = 20;
const MAX_ZOOM = 5.0;
const MIN_ZOOM = 0.2;
const ZOOM_STEP = 0.25;

function initResultsWorkspace(data) {
    const modelNameElement = document.getElementById('workstationModelName');
    if (modelNameElement) modelNameElement.textContent = data.provenance?.model_name || 'U-Net';

    // Populate Case Context Strip
    const elPid = document.getElementById('viewerPatientId');
    const elCode = document.getElementById('viewerStudyCode');
    const elDate = document.getElementById('viewerStudyDate');
    const elInd = document.getElementById('viewerIndication');
    const elMod = document.getElementById('viewerModality');

    if (elPid) elPid.innerText = (typeof currentCase !== 'undefined' && currentCase && currentCase.patient_id) ? currentCase.patient_id : 'BN-VINMEC-9284';
    if (elCode) elCode.innerText = (typeof currentCase !== 'undefined' && currentCase && currentCase.study_code) ? currentCase.study_code : (data.study_id ? data.study_id.substring(0, 14) : 'STD-260829-A1B2');
    if (elDate) elDate.innerText = (typeof currentCase !== 'undefined' && currentCase && currentCase.study_date) ? currentCase.study_date : new Date().toISOString().split('T')[0];
    if (elInd) elInd.innerText = (typeof currentCase !== 'undefined' && currentCase && (currentCase.clinical_indication || currentCase.clinical_notes)) ? (currentCase.clinical_indication || currentCase.clinical_notes) : 'Theo dõi u nang buồng trứng';
    if (elMod) elMod.innerText = (typeof currentCase !== 'undefined' && currentCase && currentCase.probe_type) ? (currentCase.probe_type === 'TRANSVAGINAL_2D' ? 'Siêu âm đầu dò âm đạo (TVUS 2D)' : currentCase.probe_type) : 'Siêu âm đầu dò âm đạo (TVUS 2D)';

    const elOvarySide = document.getElementById('viewerOvarySideBadge');
    const elContralateral = document.getElementById('viewerContralateralBadge');

    const ovarySide = (typeof currentCase !== 'undefined' && currentCase && currentCase.ovary_side) ? currentCase.ovary_side : 'RIGHT';
    const contraStatus = (typeof currentCase !== 'undefined' && currentCase && currentCase.contralateral_status) ? currentCase.contralateral_status : 'NOT_VISUALIZED';

    if (elOvarySide) {
        elOvarySide.innerText = ovarySide === 'LEFT' ? 'Buồng Trứng Trái (LO)' : 'Buồng Trứng Phải (RO)';
        elOvarySide.className = 'badge badge-cyan';
    }

    if (elContralateral) {
        if (contraStatus === 'NORMAL') {
            elContralateral.innerText = 'Đối bên: Bình thường';
            elContralateral.className = 'badge badge-success';
        } else if (contraStatus === 'SUSPECTED') {
            elContralateral.innerText = 'Đối bên: Nghi ngờ u';
            elContralateral.className = 'badge badge-danger';
        } else {
            elContralateral.innerText = 'Đối bên: Chưa quan sát';
            elContralateral.className = 'badge badge-warning';
        }
    }

    const meas = data.measurements || {};
    const calibrated = meas.calibrated === true;
    const dmax = calibrated && typeof meas.max_diameter_mm === 'number' ? meas.max_diameter_mm.toFixed(1) : null;
    const dorth = calibrated && typeof meas.ortho_diameter_mm === 'number' ? meas.ortho_diameter_mm.toFixed(1) : null;
    const dmaxNum = parseFloat(dmax) || 0;
    const dorthNum = parseFloat(dorth) || 0;
    const d3Default = calibrated && meas.d3_mm ? (typeof meas.d3_mm === 'number' ? meas.d3_mm.toFixed(1) : meas.d3_mm) : (calibrated && dmaxNum > 0 ? parseFloat(((dmaxNum + dorthNum) / 2.0).toFixed(1)) : "");
    const areaVal = calibrated && typeof meas.total_area_cm2 === 'number' ? meas.total_area_cm2.toFixed(2) : null;

    document.getElementById('resDmax').innerText = dmax === null ? 'Chưa hiệu chuẩn' : `${dmax} mm`;
    document.getElementById('resDorth').innerText = dorth === null ? 'Chưa hiệu chuẩn' : `${dorth} mm`;
    document.getElementById('inputD3').value = d3Default;
    document.getElementById('resArea').innerText = areaVal === null ? 'Chưa hiệu chuẩn' : `${areaVal} cm²`;
    
    currentCase.d3_mm = d3Default ? parseFloat(d3Default) : null;
    recalculateVolume();

    // Display AI Confidence & Quality Gate
    const badgeConf = document.getElementById('badgeConfidence');
    const isQualityPassed = data.quality_gate ? data.quality_gate.passed : (data.confidence_score >= 0.70);
    
    if (badgeConf) {
        badgeConf.innerText = `Độ tin cậy AI: ${(data.confidence_score * 100).toFixed(1)}%`;
        if (!isQualityPassed) {
            badgeConf.style.background = '#fef2f2';
            badgeConf.style.color = '#dc2626';
            badgeConf.style.border = '1px solid #fecaca';
        } else {
            badgeConf.style.background = '#e0f2fe';
            badgeConf.style.color = '#0369a1';
            badgeConf.style.border = '1px solid #bae6fd';
        }
    }

    // Display Uncertainty & Quality Gate Clinical Alert
    const uncertEl = document.getElementById('hudUncertaintyBadge');
    if (uncertEl) {
        if (data.quality_gate && !data.quality_gate.passed) {
            const failReason = (data.confidence_score < 0.70) ? '< 70%' : 'Bất định';
            uncertEl.innerText = `Quality Gate: ${failReason}`;
            uncertEl.style.background = '#fef2f2';
            uncertEl.style.color = '#991b1b';
            uncertEl.style.border = '1px solid #fecaca';
            uncertEl.style.display = 'inline-block';
        } else if (data.uncertainty) {
            uncertEl.innerText = `Bất định: ${data.uncertainty.uncertainty_level}`;
            uncertEl.style.background = '#fef3c7';
            uncertEl.style.color = '#92400e';
            uncertEl.style.border = '1px solid #fde68a';
            uncertEl.style.display = 'inline-block';
        }
    }

    const alertEl = document.getElementById('clinicalUncertaintyAlert');
    if (alertEl) {
        if (data.quality_gate && !data.quality_gate.passed) {
            alertEl.innerHTML = `<strong>⚠️ Chú ý Quality Gate:</strong> ${data.quality_gate.alert}`;
            alertEl.style.display = 'block';
            alertEl.style.background = '#fef2f2';
            alertEl.style.borderLeftColor = '#ef4444';
            alertEl.style.color = '#991b1b';
        } else if (data.uncertainty && data.uncertainty.is_uncertain) {
            alertEl.innerHTML = `<strong>⚠️ Lưu ý Bác sĩ:</strong> ${data.uncertainty.clinical_alert}`;
            alertEl.style.display = 'block';
            alertEl.style.background = '#fff7ed';
            alertEl.style.borderLeftColor = '#f97316';
            alertEl.style.color = '#9a3412';
        } else {
            alertEl.style.display = 'none';
        }
    }

    // Display Model Provenance (Compact string to avoid line breaking)
    if (data.provenance) {
        const provEl = document.getElementById('hudProvenanceTag');
        if (provEl) {
            const shortSum = data.provenance.model_checksum ? data.provenance.model_checksum.substring(0, 8) : 'v1.2';
            provEl.innerText = `U-Net • ${shortSum}`;
            provEl.title = `${data.provenance.model_name || 'Standard U-Net (Baseline)'} (SHA256: ${data.provenance.model_checksum || ''})`;
        }
    }

    const badgeSpacing = document.getElementById('badgePixelSpacing');
    if (badgeSpacing) {
        badgeSpacing.innerText = calibrated ? '📐 Đã hiệu chuẩn mm' : '📐 Chưa hiệu chuẩn mm';
    }

    // This model predicts a binary mask only; no pathology or O-RADS inference is available.
    const selectElem = document.getElementById('selectPathology');
    if (selectElem) selectElem.value = '';
    resetZoomCanvas();
    setCanvasViewMode(currentViewMode);

    // Load Background & Mask
    const onBgImageLoaded = () => {
        renderMask(data);
        saveLocalDraft();
    };

    bgImage.onload = onBgImageLoaded;
    bgImage.src = data.original_image_base64 || (typeof currentCase !== 'undefined' && currentCase && (currentCase.original_image_base64 || currentCase.image_base64)) || '';
    if (bgImage.complete && bgImage.naturalWidth > 0) {
        onBgImageLoaded();
    }
}

function setCanvasViewMode(mode) {
            currentViewMode = mode;
            const btnSingle = document.getElementById('btnModeSingle');
            const btnSplit = document.getElementById('btnModeSplit');
            const btnCurtain = document.getElementById('btnModeCurtain');

            if (btnSingle) btnSingle.classList.toggle('active', mode === 'single');
            if (btnSplit) btnSplit.classList.toggle('active', mode === 'split');
            if (btnCurtain) btnCurtain.classList.toggle('active', mode === 'curtain');

            const singleContainer = document.getElementById('canvasContainer');
            const splitContainer = document.getElementById('splitCanvasContainer');
            const curtainDiv = document.getElementById('curtainDivider');

            if (mode === 'single') {
                if (singleContainer) singleContainer.style.display = 'flex';
                if (splitContainer) splitContainer.style.display = 'none';
                if (curtainDiv) curtainDiv.style.display = 'none';
            } else if (mode === 'split') {
                if (singleContainer) singleContainer.style.display = 'none';
                if (splitContainer) splitContainer.style.display = 'grid';
                if (curtainDiv) curtainDiv.style.display = 'none';
            } else if (mode === 'curtain') {
                if (singleContainer) singleContainer.style.display = 'flex';
                if (splitContainer) splitContainer.style.display = 'none';
                if (curtainDiv) curtainDiv.style.display = 'block';
                updateCurtainPosition();
            }

            redrawMainCanvas();
            showToast(`Chế độ xem: ${mode === 'single' ? 'Khung đơn 1 màn hình' : (mode === 'split' ? 'Song song 2 màn hình (Side-by-Side)' : 'Thanh trượt so sánh rèm kéo (Curtain)')}`);
        }

function setupCurtainDrag() {
            const divider = document.getElementById('curtainDivider');
            const container = document.getElementById('canvasContainer');
            if (!divider || !container) return;

            divider.addEventListener('mousedown', (e) => {
                if (currentViewMode !== 'curtain') return;
                isDraggingCurtain = true;
                e.preventDefault();
            });

            window.addEventListener('mousemove', (e) => {
                if (!isDraggingCurtain || currentViewMode !== 'curtain') return;
                const rect = container.getBoundingClientRect();
                const clientX = Math.max(rect.left, Math.min(e.clientX, rect.right));
                curtainSplitPercent = Math.max(5, Math.min(95, ((clientX - rect.left) / rect.width) * 100));
                updateCurtainPosition();
                redrawMainCanvas();
            });

            window.addEventListener('mouseup', () => {
                if (isDraggingCurtain) {
                    isDraggingCurtain = false;
                }
            });
        }

function updateCurtainPosition() {
            const divider = document.getElementById('curtainDivider');
            if (divider) {
                divider.style.left = `${curtainSplitPercent}%`;
            }
        }

function zoomInCanvas() {
            if (currentZoom < MAX_ZOOM) {
                currentZoom = Math.min(MAX_ZOOM, parseFloat((currentZoom + ZOOM_STEP).toFixed(2)));
                applyCanvasZoom();
            }
        }

function zoomOutCanvas() {
            if (currentZoom > MIN_ZOOM) {
                currentZoom = Math.max(MIN_ZOOM, parseFloat((currentZoom - ZOOM_STEP).toFixed(2)));
                applyCanvasZoom();
            }
        }

function resetZoomCanvas() {
            currentZoom = 1.0;
            panOffsetX = 0;
            panOffsetY = 0;
            applyCanvasZoom();
        }

function applyCanvasZoom() {
            canvas.style.transform = `translate(${panOffsetX}px, ${panOffsetY}px) scale(${currentZoom})`;
            document.getElementById('zoomLevelDisplay').innerText = `${Math.round(currentZoom * 100)}%`;
            document.getElementById('hudZoom').innerText = `${currentZoom.toFixed(1)}x`;
            showToast(`Tỉ lệ phóng to Canvas: ${Math.round(currentZoom * 100)}%`);
        }

function setupCanvasZoomAndPan() {
            const container = document.getElementById('canvasContainer');
            if (container) {
                container.addEventListener('wheel', (e) => {
                    e.preventDefault();
                    if (e.deltaY < 0) {
                        zoomInCanvas();
                    } else {
                        zoomOutCanvas();
                    }
                }, { passive: false });
            }
        }

function renderMask(data) {
    if (!data) return;
    maskCtx.clearRect(0, 0, 512, 512);

    if (data.prediction_mask_base64 || data.mask_base64) {
        const maskImg = new Image();
        maskImg.onload = () => {
            const tempC = document.createElement('canvas');
            tempC.width = 512;
            tempC.height = 512;
            const tCtx = tempC.getContext('2d');
            tCtx.drawImage(maskImg, 0, 0, 512, 512);
            const idata = tCtx.getImageData(0, 0, 512, 512);
            for (let i = 0; i < idata.data.length; i += 4) {
                if (idata.data[i] > 20 || idata.data[i + 1] > 20 || idata.data[i + 2] > 20) {
                    idata.data[i] = 6;       // Cyan R
                    idata.data[i + 1] = 182; // Cyan G
                    idata.data[i + 2] = 212; // Cyan B
                    idata.data[i + 3] = 255; // Alpha
                } else {
                    idata.data[i + 3] = 0;
                }
            }
            maskCtx.putImageData(idata, 0, 0);
            saveCanvasHistory();
            redrawMainCanvas();
            calculateLiveMetrics();
        };
        maskImg.src = data.prediction_mask_base64 || data.mask_base64;
    } else if (data.rle_mask) {
        renderMaskFromRLE(data.rle_mask);
        saveCanvasHistory();
        redrawMainCanvas();
        calculateLiveMetrics();
    }
}

function renderMaskFromRLE(rle) {
            maskCtx.clearRect(0, 0, 512, 512);
            if (!rle || !rle.counts || rle.counts.length === 0) return;

            const counts = rle.counts;
            const imgData = maskCtx.createImageData(512, 512);
            let pIdx = 0;
            let val = rle.first_val || 0;

            for (let c of counts) {
                for (let i = 0; i < c; i++) {
                    if (val === 1) {
                        const idx = pIdx * 4;
                        imgData.data[idx] = 6;        // Cyan R
                        imgData.data[idx + 1] = 182;  // G
                        imgData.data[idx + 2] = 212;  // B
                        imgData.data[idx + 3] = 255;  // Alpha
                    }
                    pIdx++;
                }
                val = 1 - val;
            }
            maskCtx.putImageData(imgData, 0, 0);
        }

window.activeLayers = { original: true, gt: false, ai: true, doc: true };
window.groundTruthCanvas = null;

function toggleLayer(layerName) {
    const key = layerName.toLowerCase();
    if (window.activeLayers[key] !== undefined) {
        window.activeLayers[key] = !window.activeLayers[key];
    }
    const btn = document.getElementById(`btnLayer${layerName}`);
    if (btn) {
        btn.classList.toggle('active', !!window.activeLayers[key]);
    }
    redrawMainCanvas();
}

function calculateLiveMetrics() {
    if (!window.groundTruthCanvas) {
        const elPill = document.getElementById('liveMetricsPill');
        if (elPill) elPill.style.display = 'none';
        return;
    }
    try {
        const mCtx = maskCanvas.getContext('2d');
        const gtCtx = window.groundTruthCanvas.getContext('2d');
        const mData = mCtx.getImageData(0, 0, 512, 512).data;
        const gtData = gtCtx.getImageData(0, 0, 512, 512).data;

        let tp = 0, fp = 0, fn = 0;
        for (let i = 3; i < mData.length; i += 4) {
            const mVal = mData[i] > 20 ? 1 : 0;
            const gtVal = gtData[i] > 20 ? 1 : 0;
            if (mVal && gtVal) tp++;
            else if (mVal && !gtVal) fp++;
            else if (!mVal && gtVal) fn++;
        }

        let dice = 0.0, iou = 0.0;
        if (tp + fp + fn === 0) {
            dice = 1.0;
            iou = 1.0;
        } else {
            dice = (2.0 * tp) / (2.0 * tp + fp + fn);
            iou = tp / (tp + fp + fn);
        }

        const elPill = document.getElementById('liveMetricsPill');
        const elDice = document.getElementById('liveDiceVal');
        const elIou = document.getElementById('liveIouVal');
        if (elPill && elDice && elIou) {
            elPill.style.display = 'inline-flex';
            elDice.innerText = dice.toFixed(3);
            elIou.innerText = iou.toFixed(3);
        }
    } catch (e) {
        console.warn("Live metrics calculation note:", e);
    }
}

function redrawMainCanvas() {
    // 1. Redraw Single/Main Canvas
    ctx.clearRect(0, 0, 512, 512);

    // 1.1 Draw base ultrasound image
    if (window.activeLayers.original && bgImage && bgImage.src && (bgImage.naturalWidth > 0 || bgImage.complete)) {
        try {
            ctx.drawImage(bgImage, 0, 0, 512, 512);
        } catch (e) {
            console.error("Canvas drawImage notice:", e);
        }
    }

    // 1.2 Draw Ground Truth layer (if active and available)
    if (window.activeLayers.gt && window.groundTruthCanvas) {
        ctx.save();
        ctx.globalAlpha = maskOpacity * 0.85;
        ctx.drawImage(window.groundTruthCanvas, 0, 0);
        ctx.restore();
    }

    // 1.3 Draw mask layer (AI or Doctor Canvas)
    const showMask = isMaskVisible && (window.activeLayers.ai || window.activeLayers.doc);
    if (currentViewMode === 'curtain') {
        // Curtain clip on the right side of curtainSplitPercent
        const splitPx = (curtainSplitPercent / 100.0) * 512;
        ctx.save();
        ctx.beginPath();
        ctx.rect(splitPx, 0, 512 - splitPx, 512);
        ctx.clip();

        if (showMask) {
            ctx.globalAlpha = maskOpacity;
            ctx.drawImage(maskCanvas, 0, 0);
        }
        drawCalipersOnContext(ctx);
        ctx.restore();

        // Draw hairline on canvas
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.7)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(splitPx, 0);
        ctx.lineTo(splitPx, 512);
        ctx.stroke();

    } else {
        if (showMask) {
            ctx.save();
            ctx.globalAlpha = maskOpacity;
            ctx.drawImage(maskCanvas, 0, 0);
            ctx.restore();
        }
        drawCalipersOnContext(ctx);
    }

    // 2. Split-Screen Mode Dual Rendering
    const origCanvas = document.getElementById('originalCanvas');
    const splitEditCanvas = document.getElementById('splitEditorCanvas');
    if (origCanvas && splitEditCanvas && bgImage && bgImage.src) {
        const oCtx = origCanvas.getContext('2d');
        oCtx.clearRect(0, 0, 512, 512);
        if (window.activeLayers.original) {
            oCtx.drawImage(bgImage, 0, 0, 512, 512);
        }
        if (window.activeLayers.gt && window.groundTruthCanvas) {
            oCtx.save();
            oCtx.globalAlpha = maskOpacity * 0.85;
            oCtx.drawImage(window.groundTruthCanvas, 0, 0);
            oCtx.restore();
        }

        const seCtx = splitEditCanvas.getContext('2d');
        seCtx.clearRect(0, 0, 512, 512);
        if (window.activeLayers.original) {
            seCtx.drawImage(bgImage, 0, 0, 512, 512);
        }
        if (showMask) {
            seCtx.save();
            seCtx.globalAlpha = maskOpacity;
            seCtx.drawImage(maskCanvas, 0, 0);
            seCtx.restore();
        }
        drawCalipersOnContext(seCtx);
    }
}

function drawCalipersOnContext(targetCtx) {
    // Physical calipers are unavailable without verified pixel spacing.
    if (!currentPrediction?.pixel_spacing_mm) return;
    if (currentPrediction && currentPrediction.measurements) {
        const lesions = currentPrediction.measurements.lesions || [];
        if (lesions.length === 0) return;

        targetCtx.save();
        targetCtx.shadowColor = 'rgba(0, 0, 0, 0.9)';
        targetCtx.shadowBlur = 4;
        targetCtx.shadowOffsetX = 1;
        targetCtx.shadowOffsetY = 1;

        // Clinical standard: Draw calipers on the primary (dominant) lesion
        const primaryLesion = lesions.reduce((maxL, l) => (l.area_cm2 > maxL.area_cm2 ? l : maxL), lesions[0]);

        // Draw D1 (Max Diameter) in Yellow
        if (primaryLesion.caliper_dmax_points && primaryLesion.caliper_dmax_points.length === 2) {
            const [p1, p2] = primaryLesion.caliper_dmax_points;
            targetCtx.strokeStyle = '#facc15';
            targetCtx.lineWidth = 2;
            targetCtx.beginPath();
            targetCtx.moveTo(p1[0], p1[1]);
            targetCtx.lineTo(p2[0], p2[1]);
            targetCtx.stroke();

            drawCrosshair(targetCtx, p1[0], p1[1], '#facc15');
            drawCrosshair(targetCtx, p2[0], p2[1], '#facc15');

            const d1Val = typeof primaryLesion.max_diameter_mm === 'number' ? primaryLesion.max_diameter_mm.toFixed(1) : primaryLesion.max_diameter_mm;
            targetCtx.fillStyle = '#facc15';
            targetCtx.font = 'bold 11px JetBrains Mono, monospace';
            const labelX = Math.max(10, Math.min(460, (primaryLesion.center ? primaryLesion.center[0] : (p1[0] + p2[0])/2) - 25));
            const labelY = Math.max(15, Math.min(495, (primaryLesion.center ? primaryLesion.center[1] : (p1[1] + p2[1])/2) - 8));
            targetCtx.fillText(`D1: ${d1Val}mm`, labelX, labelY);
        }

        // Draw D2 (Orthogonal Diameter) in Cyan
        if (primaryLesion.caliper_dorth_points && primaryLesion.caliper_dorth_points.length === 2) {
            const [p1, p2] = primaryLesion.caliper_dorth_points;
            targetCtx.strokeStyle = '#38bdf8';
            targetCtx.lineWidth = 1.5;
            targetCtx.beginPath();
            targetCtx.moveTo(p1[0], p1[1]);
            targetCtx.lineTo(p2[0], p2[1]);
            targetCtx.stroke();

            drawCrosshair(targetCtx, p1[0], p1[1], '#38bdf8');
            drawCrosshair(targetCtx, p2[0], p2[1], '#38bdf8');

            const d2Val = typeof primaryLesion.ortho_diameter_mm === 'number' ? primaryLesion.ortho_diameter_mm.toFixed(1) : primaryLesion.ortho_diameter_mm;
            targetCtx.fillStyle = '#38bdf8';
            targetCtx.font = 'bold 10.5px JetBrains Mono, monospace';
            const d2LabelX = Math.max(10, Math.min(460, p2[0] + 5));
            const d2LabelY = Math.max(15, Math.min(495, p2[1] + 12));
            targetCtx.fillText(`D2: ${d2Val}mm`, d2LabelX, d2LabelY);
        }

        targetCtx.restore();
    }
}

function drawCrosshair(c, x, y, color = '#facc15') {
    c.strokeStyle = color;
    c.lineWidth = 2;
    c.beginPath();
    c.moveTo(x - 4, y); c.lineTo(x + 4, y);
    c.moveTo(x, y - 4); c.lineTo(x, y + 4);
    c.stroke();
}

function setupCanvasEngine() {
    canvas = document.getElementById('editorCanvas');
    if (canvas) {
        ctx = canvas.getContext('2d');

        // Main editor canvas listener
        canvas.addEventListener('mousedown', (e) => {
            if (e.shiftKey && currentZoom > 1) {
                e.preventDefault();
                isPanning = true;
                startPanX = e.clientX - panOffsetX;
                startPanY = e.clientY - panOffsetY;
                canvas.style.cursor = 'grabbing';
                return;
            }
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            lastX = (e.clientX - rect.left) * scaleX;
            lastY = (e.clientY - rect.top) * scaleY;
            isDrawing = true;
            paintOnMask(lastX, lastY);
        });

        canvas.addEventListener('mousemove', (e) => {
            if (isPanning) {
                panOffsetX = e.clientX - startPanX;
                panOffsetY = e.clientY - startPanY;
                applyCanvasZoom();
                return;
            }
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            const curX = (e.clientX - rect.left) * scaleX;
            const curY = (e.clientY - rect.top) * scaleY;

            const hud = document.getElementById('hudCoords');
            if (hud) hud.innerText = `X: ${Math.round(curX)} Y: ${Math.round(curY)}`;

            if (isDrawing) {
                paintOnMask(curX, curY, lastX, lastY);
                lastX = curX;
                lastY = curY;
            }
        });
    }

            // Split editor canvas listener (allows drawing in split mode)
            const splitEditCanvas = document.getElementById('splitEditorCanvas');
            if (splitEditCanvas) {
                splitEditCanvas.addEventListener('mousedown', (e) => {
                    const rect = splitEditCanvas.getBoundingClientRect();
                    const scaleX = splitEditCanvas.width / rect.width;
                    const scaleY = splitEditCanvas.height / rect.height;
                    lastX = (e.clientX - rect.left) * scaleX;
                    lastY = (e.clientY - rect.top) * scaleY;
                    isDrawing = true;
                    paintOnMask(lastX, lastY);
                });

                splitEditCanvas.addEventListener('mousemove', (e) => {
                    const rect = splitEditCanvas.getBoundingClientRect();
                    const scaleX = splitEditCanvas.width / rect.width;
                    const scaleY = splitEditCanvas.height / rect.height;
                    const curX = (e.clientX - rect.left) * scaleX;
                    const curY = (e.clientY - rect.top) * scaleY;

                    document.getElementById('hudCoords').innerText = `X: ${Math.round(curX)} Y: ${Math.round(curY)}`;

                    if (isDrawing) {
                        paintOnMask(curX, curY, lastX, lastY);
                        lastX = curX;
                        lastY = curY;
                    }
                });
            }

            window.addEventListener('mouseup', () => {
                if (isPanning) {
                    isPanning = false;
                    canvas.style.cursor = '';
                    return;
                }
                if (isDrawing) {
                    isDrawing = false;
                    saveCanvasHistory();
                    chooseDoctorAction('MODIFIED');
                    document.getElementById('hudStatus').innerText = 'Đã chỉnh sửa';
                    document.getElementById('hudStatus').style.color = 'var(--vm-accent-amber)';
                    recalculateClientCalipersFromMask();
                    saveLocalDraft();
                }
            });
        }

function paintOnMask(x, y, prevX = null, prevY = null) {
            maskCtx.save();
            maskCtx.lineCap = 'round';
            maskCtx.lineJoin = 'round';
            maskCtx.lineWidth = brushSize;

            if (currentTool === 'brush') {
                maskCtx.strokeStyle = 'rgb(6, 182, 212)';
                maskCtx.fillStyle = 'rgb(6, 182, 212)';
                maskCtx.globalCompositeOperation = 'source-over';
            } else if (currentTool === 'eraser') {
                maskCtx.strokeStyle = 'rgba(0, 0, 0, 1)';
                maskCtx.fillStyle = 'rgba(0, 0, 0, 1)';
                maskCtx.globalCompositeOperation = 'destination-out';
            }

            if (typeof prevX === 'number' && typeof prevY === 'number') {
                maskCtx.beginPath();
                maskCtx.moveTo(prevX, prevY);
                maskCtx.lineTo(x, y);
                maskCtx.stroke();
            } else {
                maskCtx.beginPath();
                maskCtx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
                maskCtx.fill();
            }
            maskCtx.restore();

            redrawMainCanvas();
        }

function recalculateClientCalipersFromMask() {
    // Preserve the edited binary mask. MMOTU does not include physical pixel spacing.
}

function recalculateVolume() {
            const meas = currentPrediction ? (currentPrediction.measurements || {}) : {};
            const dmax = meas.max_diameter_mm || 0;
            const dorth = meas.ortho_diameter_mm || 0;
            const d3 = currentCase.d3_mm || (document.getElementById('inputD3') ? parseFloat(document.getElementById('inputD3').value) || 0 : 0);

            if (dmax > 0 && dorth > 0 && d3 > 0) {
                // ISUOG Ellipsoid formula: V = 0.523 * D1 * D2 * D3 / 1000 mL
                const vol = parseFloat((0.523 * (dmax * dorth * d3) / 1000.0).toFixed(2));
                document.getElementById('resVolume').innerText = `${vol} mL`;
                currentCase.volume_cm3 = vol;
            } else {
                document.getElementById('resVolume').innerText = 'Chưa hiệu chuẩn';
                currentCase.volume_cm3 = null;
            }
        }

function onD3Changed(val) {
            const d3 = parseFloat(val) || 0;
            currentCase.d3_mm = d3;
            recalculateVolume();
            saveLocalDraft();
}

function setupDualViewer() {
    for (const side of ['R', 'L']) {
        const viewport = document.getElementById(`dualViewport${side}`);
        const canvas = document.getElementById(`dualCanvas${side}`);
        viewport.addEventListener('click', () => selectDualViewport(side));
        canvas.addEventListener('pointerdown', event => dualPointerDown(side, event));
        canvas.addEventListener('pointermove', event => dualPointerMove(side, event));
        canvas.addEventListener('pointerup', event => dualPointerUp(side, event));
        canvas.addEventListener('pointercancel', event => dualPointerUp(side, event));
        canvas.closest('.pacs-canvas-frame').addEventListener('wheel', event => {
            event.preventDefault();
            selectDualViewport(side);
            zoomDual(event.deltaY < 0 ? 0.25 : -0.25);
        }, { passive: false });
        document.getElementById(`dualNotes${side}`).addEventListener('input', () => {
            if (dualCase.sides[side].approved) invalidateDualApproval(side);
        });
    }
    window.addEventListener('keydown', event => {
        if (!document.getElementById('screenDualResults').classList.contains('active')) return;
        const tag = event.target.tagName;
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;
        if (event.key === 'Tab') {
            if (!event.target.closest('.pacs-viewport')) return;
            event.preventDefault();
            const next = dualCase.active === 'R' ? 'L' : 'R';
            selectDualViewport(next);
            document.getElementById(`dualViewport${next}`).focus();
        } else if (event.key === '[' || event.key === ']') {
            event.preventDefault();
            selectDualViewport(dualCase.active === 'R' ? 'L' : 'R');
        } else if (event.key.toLowerCase() === 'b') setDualTool('brush');
        else if (event.key.toLowerCase() === 'e') setDualTool('eraser');
        else if (event.key.toLowerCase() === 'm') toggleDualMask();
        else if (event.ctrlKey && event.key.toLowerCase() === 'z') {
            event.preventDefault();
            if (event.shiftKey) redoDualMask(); else undoDualMask();
        }
    });
}

function dualMaskFromRle(rle) {
    if (!rle || rle.shape?.[0] !== 512 || rle.shape?.[1] !== 512 || !Array.isArray(rle.counts)) {
        throw new Error('Mask dự đoán không đúng kích thước 512 × 512.');
    }
    const mask = document.createElement('canvas');
    mask.width = mask.height = 512;
    const context = mask.getContext('2d');
    const pixels = context.createImageData(512, 512);
    let offset = 0;
    let value = rle.first_val === 1 ? 1 : 0;
    for (const count of rle.counts) {
        if (!Number.isInteger(count) || count <= 0 || offset + count > 512 * 512) {
            throw new Error('Dữ liệu RLE của mask không hợp lệ.');
        }
        if (value) {
            for (let i = offset; i < offset + count; i++) {
                const j = i * 4;
                pixels.data[j] = 6;
                pixels.data[j + 1] = 182;
                pixels.data[j + 2] = 212;
                pixels.data[j + 3] = 255;
            }
        }
        offset += count;
        value = 1 - value;
    }
    if (offset !== 512 * 512) throw new Error('Mask RLE chưa bao phủ toàn bộ ảnh.');
    context.putImageData(pixels, 0, 0);
    return mask;
}

async function prepareDualSide(side) {
    const item = dualCase.sides[side];
    item.mask = dualMaskFromRle(item.prediction.rle_mask);
    item.undo = [item.mask.getContext('2d').getImageData(0, 0, 512, 512)];
    item.redo = [];
    item.reviewStartedAt = performance.now();
    item.original = await new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error(`Không thể hiển thị ảnh bên ${side}.`));
        image.src = item.prediction.original_image_base64;
    });
    document.getElementById(`dualStatus${side}`).textContent = 'Chờ chuyên viên rà soát';
    renderDualSide(side);
}

function selectDualViewport(side) {
    dualCase.active = side;
    for (const name of ['R', 'L']) document.getElementById(`dualViewport${name}`).classList.toggle('is-selected', name === side);
    const item = dualCase.sides[side];
    document.getElementById('dualBrightness').value = item.brightness;
    document.getElementById('dualContrast').value = item.contrast;
}

function renderDualSide(side) {
    const item = dualCase.sides[side];
    const canvas = document.getElementById(`dualCanvas${side}`);
    if (!item.original || !item.mask) return;
    const context = canvas.getContext('2d');
    context.clearRect(0, 0, 512, 512);
    if (dualCase.layerMode !== 'mask') {
        context.save();
        context.filter = `brightness(${item.brightness}%) contrast(${item.contrast}%)`;
        context.drawImage(item.original, 0, 0, 512, 512);
        context.restore();
    }
    if (dualCase.showMask && dualCase.layerMode !== 'original') {
        context.save();
        context.globalAlpha = dualCase.layerMode === 'mask' ? 1 : dualCase.opacity;
        context.drawImage(item.mask, 0, 0);
        context.restore();
    }
    canvas.style.transform = `translate(${item.panX}px, ${item.panY}px) scale(${item.zoom})`;
    document.getElementById(`dualZoom${side}`).textContent = `${Math.round(item.zoom * 100)}%`;
    document.getElementById(`dualLayer${side}`).textContent = dualCase.layerMode === 'mask' ? 'Mask' : dualCase.layerMode === 'original' ? 'Original' : 'Original + Mask';
}

function renderDualComparison() {
    for (const side of ['R', 'L']) {
        const prediction = dualCase.sides[side].prediction;
        if (!prediction) continue;
        const metrics = prediction.measurements || {};
        const calibrated = metrics.calibrated === true;
        document.getElementById(`dualLesions${side}`).textContent = Number.isInteger(metrics.total_lesions) ? String(metrics.total_lesions) : '—';
        document.getElementById(`dualDiameters${side}`).textContent = calibrated && Number.isFinite(metrics.max_diameter_mm) && Number.isFinite(metrics.ortho_diameter_mm)
            ? `${metrics.max_diameter_mm.toFixed(1)} × ${metrics.ortho_diameter_mm.toFixed(1)} × ${Number.isFinite(metrics.d3_mm) ? metrics.d3_mm.toFixed(1) : '—'}` : 'Chưa hiệu chuẩn';
        document.getElementById(`dualVolume${side}`).textContent = calibrated && Number.isFinite(metrics.total_volume_cm3)
            ? metrics.total_volume_cm3.toFixed(2) : '—';
        document.getElementById(`dualConfidence${side}`).textContent = Number.isFinite(prediction.confidence_score)
            ? `${(prediction.confidence_score * 100).toFixed(1)}%` : '—';
        document.getElementById(`dualClinical${side}`).textContent = 'Chờ đánh giá chuyên môn';
    }
}

function setDualViewMode(mode) {
    if (!['split', 'R', 'L'].includes(mode)) return;
    dualCase.mode = mode;
    const grid = document.getElementById('dualViewportGrid');
    grid.className = `pacs-viewport-grid ${mode === 'split' ? '' : `focus-${mode}`}`;
    for (const name of ['Split', 'R', 'L']) document.getElementById(`dualMode${name}`).classList.toggle('is-active', mode === (name === 'Split' ? 'split' : name));
    if (mode !== 'split') selectDualViewport(mode);
}

function setDualLayerMode(mode) {
    if (!['original', 'mask', 'overlay'].includes(mode)) return;
    dualCase.layerMode = mode;
    dualCase.showMask = mode !== 'original';
    for (const name of ['Original', 'Mask', 'Overlay']) document.getElementById(`dualView${name}`).classList.toggle('is-active', name.toLowerCase() === mode);
    const maskBtn = document.getElementById('dualMaskBtn');
    maskBtn.setAttribute('aria-pressed', String(dualCase.showMask));
    maskBtn.textContent = dualCase.showMask ? 'M · Mask' : 'M · Mask tắt';
    for (const side of ['R', 'L']) renderDualSide(side);
}

function toggleDualMask() { setDualLayerMode(dualCase.showMask ? 'original' : 'overlay'); }

function toggleDualSync() {
    dualCase.sync = !dualCase.sync;
    const button = document.getElementById('dualSyncBtn');
    button.classList.toggle('is-active', dualCase.sync);
    button.setAttribute('aria-pressed', String(dualCase.sync));
    if (dualCase.sync) {
        const active = dualCase.sides[dualCase.active];
        const other = dualCase.sides[dualCase.active === 'R' ? 'L' : 'R'];
        for (const key of ['zoom', 'panX', 'panY', 'brightness', 'contrast']) other[key] = active[key];
        renderDualSide(dualCase.active === 'R' ? 'L' : 'R');
    }
}

function setDualTool(tool) {
    dualCase.tool = tool;
    document.getElementById('dualBrushBtn').classList.toggle('is-active', tool === 'brush');
    document.getElementById('dualEraserBtn').classList.toggle('is-active', tool === 'eraser');
}

function setDualBrushSize(value) {
    dualCase.brushSize = Number(value);
    document.getElementById('dualBrushSizeVal').textContent = `${value} px`;
}

function setDualOpacity(value) {
    dualCase.opacity = Number(value) / 100;
    document.getElementById('dualOpacityVal').textContent = `${value}%`;
    for (const side of ['R', 'L']) renderDualSide(side);
}

function setDualLut(key, value) {
    const sides = dualCase.sync ? ['R', 'L'] : [dualCase.active];
    for (const side of sides) {
        dualCase.sides[side][key] = Number(value);
        renderDualSide(side);
    }
}

function zoomDual(delta) {
    const sides = dualCase.sync ? ['R', 'L'] : [dualCase.active];
    for (const side of sides) {
        const item = dualCase.sides[side];
        item.zoom = Math.max(0.5, Math.min(4, Math.round((item.zoom + delta) * 100) / 100));
        renderDualSide(side);
    }
}

function resetDualZoom() {
    const sides = dualCase.sync ? ['R', 'L'] : [dualCase.active];
    for (const side of sides) {
        const item = dualCase.sides[side];
        item.zoom = 1;
        item.panX = item.panY = 0;
        renderDualSide(side);
    }
}

function dualPointerPosition(side, event) {
    const rect = document.getElementById(`dualCanvas${side}`).getBoundingClientRect();
    return { x: (event.clientX - rect.left) * 512 / rect.width, y: (event.clientY - rect.top) * 512 / rect.height };
}

function dualPointerDown(side, event) {
    const item = dualCase.sides[side];
    if (!item.prediction || item.saving) return;
    selectDualViewport(side);
    event.preventDefault();
    event.target.setPointerCapture(event.pointerId);
    if (event.shiftKey) {
        item.pointer = { mode: 'pan', x: event.clientX, y: event.clientY };
    } else {
        if (dualCase.layerMode === 'original') setDualLayerMode('overlay');
        item.pointer = { mode: 'paint', ...dualPointerPosition(side, event) };
        paintDualMask(side, item.pointer.x, item.pointer.y);
    }
}

function dualPointerMove(side, event) {
    const item = dualCase.sides[side];
    if (!item.pointer) return;
    if (item.pointer.mode === 'pan') {
        const dx = event.clientX - item.pointer.x;
        const dy = event.clientY - item.pointer.y;
        for (const name of dualCase.sync ? ['R', 'L'] : [side]) {
            dualCase.sides[name].panX += dx;
            dualCase.sides[name].panY += dy;
            renderDualSide(name);
        }
        item.pointer.x = event.clientX;
        item.pointer.y = event.clientY;
    } else {
        const point = dualPointerPosition(side, event);
        paintDualMask(side, point.x, point.y, item.pointer.x, item.pointer.y);
        item.pointer.x = point.x;
        item.pointer.y = point.y;
    }
}

function dualPointerUp(side, event) {
    const item = dualCase.sides[side];
    if (!item.pointer) return;
    const painted = item.pointer.mode === 'paint';
    item.pointer = null;
    if (event.target.hasPointerCapture(event.pointerId)) event.target.releasePointerCapture(event.pointerId);
    if (painted) {
        item.undo.push(item.mask.getContext('2d').getImageData(0, 0, 512, 512));
        if (item.undo.length > 12) item.undo.shift();
        item.redo.length = 0;
        invalidateDualApproval(side);
    }
}

function paintDualMask(side, x, y, prevX, prevY) {
    const item = dualCase.sides[side];
    const context = item.mask.getContext('2d');
    context.save();
    context.globalCompositeOperation = dualCase.tool === 'eraser' ? 'destination-out' : 'source-over';
    context.strokeStyle = context.fillStyle = '#06b6d4';
    context.lineCap = context.lineJoin = 'round';
    context.lineWidth = dualCase.brushSize;
    context.beginPath();
    if (Number.isFinite(prevX) && Number.isFinite(prevY)) {
        context.moveTo(prevX, prevY);
        context.lineTo(x, y);
        context.stroke();
    } else {
        context.arc(x, y, dualCase.brushSize / 2, 0, Math.PI * 2);
        context.fill();
    }
    context.restore();
    renderDualSide(side);
}

function undoDualMask() {
    const item = dualCase.sides[dualCase.active];
    if (item.saving || item.undo.length < 2) return;
    item.redo.push(item.undo.pop());
    item.mask.getContext('2d').putImageData(item.undo[item.undo.length - 1], 0, 0);
    invalidateDualApproval(dualCase.active);
    renderDualSide(dualCase.active);
}

function redoDualMask() {
    const item = dualCase.sides[dualCase.active];
    if (item.saving || !item.redo.length) return;
    const next = item.redo.pop();
    item.undo.push(next);
    item.mask.getContext('2d').putImageData(next, 0, 0);
    invalidateDualApproval(dualCase.active);
    renderDualSide(dualCase.active);
}

function saveCanvasHistory() {
            const imgData = maskCtx.getImageData(0, 0, 512, 512);
            undoStack.push(imgData);
            if (undoStack.length > MAX_HISTORY) undoStack.shift();
            redoStack.length = 0; // Clear redo on new action
            calculateLiveMetrics();
        }

function undoCanvas() {
            if (undoStack.length > 1) {
                const current = undoStack.pop();
                redoStack.push(current);
                const prev = undoStack[undoStack.length - 1];
                maskCtx.putImageData(prev, 0, 0);
                chooseDoctorAction('MODIFIED');
                redrawMainCanvas();
                recalculateClientCalipersFromMask();
                calculateLiveMetrics();
                saveLocalDraft();
                showToast("↶ Đã hoàn tác");
            }
        }

function redoCanvas() {
            if (redoStack.length > 0) {
                const next = redoStack.pop();
                undoStack.push(next);
                maskCtx.putImageData(next, 0, 0);
                chooseDoctorAction('MODIFIED');
                redrawMainCanvas();
                recalculateClientCalipersFromMask();
                calculateLiveMetrics();
                saveLocalDraft();
                showToast("↷ Đã làm lại");
            }
        }

function resetMaskToAI() {
            if (currentPrediction) {
                chooseDoctorAction('ACCEPTED_RAW');
                document.getElementById('hudStatus').innerText = 'Khớp AI';
                document.getElementById('hudStatus').style.color = 'var(--vm-green)';
                
                // Restore original measurements
                const meas = currentPrediction.measurements || {};
                document.getElementById('resDmax').innerText = meas.calibrated ? `${meas.max_diameter_mm} mm` : 'Chưa hiệu chuẩn';
                document.getElementById('resDorth').innerText = meas.calibrated ? `${meas.ortho_diameter_mm} mm` : 'Chưa hiệu chuẩn';
                document.getElementById('resArea').innerText = meas.calibrated ? `${meas.total_area_cm2} cm²` : 'Chưa hiệu chuẩn';
                renderMask(currentPrediction);
                saveLocalDraft();
                showToast("🔄 Đã phục hồi mask AI ban đầu");
            }
        }

function setCanvasTool(tool) {
            currentTool = tool;
            document.getElementById('btnToolBrush').classList.toggle('active', tool === 'brush');
            document.getElementById('btnToolEraser').classList.toggle('active', tool === 'eraser');
        }

function onBrushSizeChange(val) {
            brushSize = parseInt(val);
            document.getElementById('valBrushSize').innerText = `${val}px`;
        }

function onOpacityChange(val) {
            maskOpacity = parseInt(val) / 100.0;
            document.getElementById('valOpacity').innerText = `${val}%`;
            redrawMainCanvas();
        }

function toggleMaskOverlay() {
            isMaskVisible = !isMaskVisible;
            redrawMainCanvas();
            showToast(isMaskVisible ? "Đã hiển thị Mask" : "Đã ẩn Mask");
        }
