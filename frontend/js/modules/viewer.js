/**
 * MODULE: VIEWER.JS
 */

const MAX_HISTORY = 20;
const MAX_ZOOM = 5.0;
const MIN_ZOOM = 0.2;
const ZOOM_STEP = 0.25;

function initResultsWorkspace(data) {
    const meas = data.measurements || {};
    const dmax = typeof meas.max_diameter_mm === 'number' ? meas.max_diameter_mm.toFixed(1) : (meas.max_diameter_mm || "0.0");
    const dorth = typeof meas.ortho_diameter_mm === 'number' ? meas.ortho_diameter_mm.toFixed(1) : (meas.ortho_diameter_mm || "0.0");
    const dmaxNum = parseFloat(dmax) || 0;
    const dorthNum = parseFloat(dorth) || 0;
    const d3Default = meas.d3_mm ? (typeof meas.d3_mm === 'number' ? meas.d3_mm.toFixed(1) : meas.d3_mm) : (dmaxNum > 0 ? parseFloat(((dmaxNum + dorthNum) / 2.0).toFixed(1)) : "0.0");
    const areaVal = typeof meas.total_area_cm2 === 'number' ? meas.total_area_cm2.toFixed(2) : (meas.total_area_cm2 || "0.00");

    document.getElementById('resDmax').innerText = `${dmax} mm`;
    document.getElementById('resDorth').innerText = `${dorth} mm`;
    document.getElementById('inputD3').value = d3Default;
    document.getElementById('resArea').innerText = `${areaVal} cm²`;
    
    currentCase.d3_mm = parseFloat(d3Default) || 0;
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
            provEl.innerText = `Attention U-Net • ${shortSum}`;
        }
    }

    // Dynamic AI Pathology Recommendation & Acoustic Profile
    const cdss = data.cdss_classification || {};
    const acoustic = data.acoustic_profile || {};
    const selectElem = document.getElementById('selectPathology');
    const aiTextElem = document.getElementById('aiSuggestedPathologyText');
    const acousticBadge = document.getElementById('aiAcousticPatternBadge');

    let suggestedPathology = cdss.primary_suspicion || (meas.total_lesions === 0 ? "Buồng trứng bình thường (Normal Control)" : "U nang thanh dịch buồng trứng (Simple Serous Cyst)");
    
    if (aiTextElem) {
        if (!isQualityPassed) {
            aiTextElem.innerHTML = `<span style="color: #dc2626; font-weight: 700;">[CHỜ DUYỆT] Bác sĩ cần thẩm định & chọn phân loại thủ công</span>`;
        } else {
            const confPct = Math.round((cdss.confidence_score || data.confidence_score || 0.9) * 100);
            const oradsTag = cdss.orads_category ? `[${cdss.orads_category}]` : '';
            aiTextElem.innerText = `${oradsTag} ${suggestedPathology} (${confPct}% tin cậy)`;
        }
    }

    if (acousticBadge) {
        acousticBadge.innerText = acoustic.echogenicity_label ? acoustic.echogenicity_label.split('(')[0].trim() : (meas.total_lesions === 0 ? 'Bình thường' : 'Dịch trong');
    }

    // Dropdown pathology selection
    if (selectElem) {
        if (!isQualityPassed) {
            selectElem.value = "U nang thanh dịch buồng trứng (Simple Serous Cyst)";
        } else if (meas.total_lesions === 0 || (suggestedPathology && suggestedPathology.includes('bình thường'))) {
            selectElem.value = "Buồng trứng bình thường (Normal Control)";
        } else if (suggestedPathology.includes('lạc nội mạc') || suggestedPathology.includes('Endometrioma')) {
            selectElem.value = "U lạc nội mạc tử cung (Endometrioma / Chocolate Cyst)";
        } else if (suggestedPathology.includes('bì') || suggestedPathology.includes('quái') || suggestedPathology.includes('Dermoid')) {
            selectElem.value = "U bì buồng trứng / U quái (Dermoid Cyst / Teratoma)";
        } else if (suggestedPathology.includes('nhầy') || suggestedPathology.includes('Mucinous')) {
            selectElem.value = "U nang nhầy buồng trứng (Mucinous Cystadenoma)";
        } else if (suggestedPathology.includes('đặc') || suggestedPathology.includes('Solid') || suggestedPathology.includes('ác tính')) {
            selectElem.value = "Khối u buồng trứng nghi ngờ / Khối đặc (Suspicious Solid Mass)";
        } else if (suggestedPathology.includes('xuất huyết')) {
            selectElem.value = "Nang xuất huyết buồng trứng (Hemorrhagic Cyst)";
        } else {
            selectElem.value = "U nang thanh dịch buồng trứng (Simple Serous Cyst)";
        }
    }

    // Update O-RADS indicator
    updateOradsIndicator(selectElem ? selectElem.value : suggestedPathology);
    resetZoomCanvas();
    setCanvasViewMode(currentViewMode);

    // Load Background & Mask
    const onBgImageLoaded = () => {
        renderMaskFromRLE(data.rle_mask);
        saveCanvasHistory();
        redrawMainCanvas();
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
            applyCanvasZoom();
        }

function applyCanvasZoom() {
            canvas.style.transform = `scale(${currentZoom})`;
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

function redrawMainCanvas() {
    // 1. Redraw Single/Main Canvas
    ctx.clearRect(0, 0, 512, 512);

    // 1.1 Draw base ultrasound image
    if (bgImage && bgImage.src && (bgImage.naturalWidth > 0 || bgImage.complete)) {
        try {
            ctx.drawImage(bgImage, 0, 0, 512, 512);
        } catch (e) {
            console.error("Canvas drawImage notice:", e);
        }
    }

    // 1.2 Draw mask layer
    if (currentViewMode === 'curtain') {
        // Curtain clip on the right side of curtainSplitPercent
        const splitPx = (curtainSplitPercent / 100.0) * 512;
        ctx.save();
        ctx.beginPath();
        ctx.rect(splitPx, 0, 512 - splitPx, 512);
        ctx.clip();

        if (isMaskVisible) {
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
        if (isMaskVisible) {
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
        // Render Original clean viewport WITHOUT AI overlays or duplicate calipers
        const oCtx = origCanvas.getContext('2d');
        oCtx.clearRect(0, 0, 512, 512);
        oCtx.drawImage(bgImage, 0, 0, 512, 512);

        // Render AI & Doctor Mask edited viewport
        const seCtx = splitEditCanvas.getContext('2d');
        seCtx.clearRect(0, 0, 512, 512);
        seCtx.drawImage(bgImage, 0, 0, 512, 512);
        if (isMaskVisible) {
            seCtx.save();
            seCtx.globalAlpha = maskOpacity;
            seCtx.drawImage(maskCanvas, 0, 0);
            seCtx.restore();
        }
        drawCalipersOnContext(seCtx);
    }
}

function drawCalipersOnContext(targetCtx) {
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
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            lastX = (e.clientX - rect.left) * scaleX;
            lastY = (e.clientY - rect.top) * scaleY;
            isDrawing = true;
            paintOnMask(lastX, lastY);
        });

        canvas.addEventListener('mousemove', (e) => {
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
            try {
                const imgData = maskCtx.getImageData(0, 0, 512, 512).data;
                let minX = 512, maxX = 0, minY = 512, maxY = 0;
                let totalPx = 0;
                for (let y = 0; y < 512; y++) {
                    for (let x = 0; x < 512; x++) {
                        const idx = (y * 512 + x) * 4;
                        if (imgData[idx + 3] > 0) { // Alpha > 0
                            totalPx++;
                            if (x < minX) minX = x;
                            if (x > maxX) maxX = x;
                            if (y < minY) minY = y;
                            if (y > maxY) maxY = y;
                        }
                    }
                }

                const pixelSpacing = 0.1; // mm/px
                if (totalPx > 20 && minX <= maxX && minY <= maxY) {
                    const wPx = maxX - minX;
                    const hPx = maxY - minY;
                    const dmaxPx = Math.max(wPx, hPx);
                    const dorthPx = Math.min(wPx, hPx);
                    const dmaxMm = parseFloat((dmaxPx * pixelSpacing).toFixed(1));
                    const dorthMm = parseFloat((dorthPx * pixelSpacing).toFixed(1));
                    const areaCm2 = parseFloat(((totalPx * pixelSpacing * pixelSpacing) / 100.0).toFixed(2));
                    const d3Mm = parseFloat(((dmaxMm + dorthMm) / 2.0).toFixed(1));
                    const volCm3 = parseFloat((0.523 * (dmaxMm * dorthMm * d3Mm) / 1000.0).toFixed(2));

                    // Update UI
                    document.getElementById('resDmax').innerText = `${dmaxMm} mm`;
                    document.getElementById('resDorth').innerText = `${dorthMm} mm`;
                    document.getElementById('resArea').innerText = `${areaCm2} cm²`;
                    document.getElementById('resVolume').innerText = `${volCm3} mL`;

                    // Update active prediction measurement structure
                    if (currentPrediction && currentPrediction.measurements) {
                        currentPrediction.measurements.max_diameter_mm = dmaxMm;
                        currentPrediction.measurements.ortho_diameter_mm = dorthMm;
                        currentPrediction.measurements.total_area_cm2 = areaCm2;
                        currentPrediction.measurements.d3_mm = d3Mm;
                        currentPrediction.measurements.total_volume_cm3 = volCm3;
                        if (currentPrediction.measurements.lesions && currentPrediction.measurements.lesions[0]) {
                            currentPrediction.measurements.lesions[0].max_diameter_mm = dmaxMm;
                            currentPrediction.measurements.lesions[0].ortho_diameter_mm = dorthMm;
                            currentPrediction.measurements.lesions[0].center = [(minX + maxX)/2, (minY + maxY)/2];
                            currentPrediction.measurements.lesions[0].caliper_dmax_points = [
                                [(minX + maxX)/2, minY],
                                [(minX + maxX)/2, maxY]
                            ];
                        }
                    }
                } else if (totalPx <= 20) {
                    document.getElementById('resDmax').innerText = `0.0 mm`;
                    document.getElementById('resDorth').innerText = `0.0 mm`;
                    document.getElementById('resArea').innerText = `0.00 cm²`;
                    document.getElementById('resVolume').innerText = `0.0 mL`;
                    if (currentPrediction && currentPrediction.measurements) {
                        currentPrediction.measurements.max_diameter_mm = 0.0;
                        currentPrediction.measurements.ortho_diameter_mm = 0.0;
                        currentPrediction.measurements.total_area_cm2 = 0.0;
                        currentPrediction.measurements.total_volume_cm3 = 0.0;
                        currentPrediction.measurements.total_lesions = 0;
                    }
                }
            } catch (err) {
                console.warn("Client caliper recalculation error:", err);
            }
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
                document.getElementById('resVolume').innerText = `0.0 mL`;
                currentCase.volume_cm3 = 0.0;
            }
        }

function onD3Changed(val) {
            const d3 = parseFloat(val) || 0;
            currentCase.d3_mm = d3;
            recalculateVolume();
            saveLocalDraft();
        }

function saveCanvasHistory() {
            const imgData = maskCtx.getImageData(0, 0, 512, 512);
            undoStack.push(imgData);
            if (undoStack.length > MAX_HISTORY) undoStack.shift();
            redoStack.length = 0; // Clear redo on new action
        }

function undoCanvas() {
            if (undoStack.length > 1) {
                const current = undoStack.pop();
                redoStack.push(current);
                const prev = undoStack[undoStack.length - 1];
                maskCtx.putImageData(prev, 0, 0);
                redrawMainCanvas();
                recalculateClientCalipersFromMask();
                saveLocalDraft();
                showToast("↶ Đã hoàn tác");
            }
        }

function redoCanvas() {
            if (redoStack.length > 0) {
                const next = redoStack.pop();
                undoStack.push(next);
                maskCtx.putImageData(next, 0, 0);
                redrawMainCanvas();
                recalculateClientCalipersFromMask();
                saveLocalDraft();
                showToast("↷ Đã làm lại");
            }
        }

function resetMaskToAI() {
            if (currentPrediction) {
                renderMaskFromRLE(currentPrediction.rle_mask);
                saveCanvasHistory();
                redrawMainCanvas();
                chooseDoctorAction('ACCEPTED_RAW');
                document.getElementById('hudStatus').innerText = 'Khớp AI';
                document.getElementById('hudStatus').style.color = 'var(--vm-green)';
                
                // Restore original measurements
                const meas = currentPrediction.measurements || {};
                document.getElementById('resDmax').innerText = `${meas.max_diameter_mm || 0} mm`;
                document.getElementById('resDorth').innerText = `${meas.ortho_diameter_mm || 0} mm`;
                document.getElementById('resArea').innerText = `${meas.total_area_cm2 || 0} cm²`;
                recalculateVolume();
                
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
