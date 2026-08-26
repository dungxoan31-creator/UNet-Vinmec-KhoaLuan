/**
 * MODULE: VIEWER.JS
 */


function initResultsWorkspace(data) {
    const meas = data.measurements || {};
    const dmax = meas.max_diameter_mm || 0;
    const dorth = meas.ortho_diameter_mm || 0;
    const d3Default = meas.d3_mm || (dmax > 0 ? parseFloat(((dmax + dorth) / 2.0).toFixed(1)) : 0);

    document.getElementById('resDmax').innerText = `${dmax} mm`;
    document.getElementById('resDorth').innerText = `${dorth} mm`;
    document.getElementById('inputD3').value = d3Default;
    document.getElementById('resArea').innerText = `${meas.total_area_cm2 || 0} cm²`;
    
    currentCase.d3_mm = d3Default;
    recalculateVolume();

    // Display AI Confidence
    const badgeConf = document.getElementById('badgeConfidence');
    if (badgeConf) {
        badgeConf.innerText = `Độ tin cậy của AI: ${(data.confidence_score * 100).toFixed(1)}%`;
    }

    // Display Uncertainty & OOD Alert
    if (data.uncertainty) {
        const uncertEl = document.getElementById('hudUncertaintyBadge');
        if (uncertEl) {
            uncertEl.innerText = `Bất định: ${data.uncertainty.uncertainty_level} (Entropy: ${data.uncertainty.entropy_score})`;
            uncertEl.style.display = 'inline-block';
        }
        const alertEl = document.getElementById('clinicalUncertaintyAlert');
        if (alertEl) {
            alertEl.innerHTML = `<strong>⚠️ Lưu ý Bác sĩ:</strong> ${data.uncertainty.clinical_alert}`;
            alertEl.style.display = data.uncertainty.is_uncertain ? 'block' : 'none';
        }
    }

    // Display Model Provenance
    if (data.provenance) {
        const provEl = document.getElementById('hudProvenanceTag');
        if (provEl) {
            const shortSum = data.provenance.model_checksum ? data.provenance.model_checksum.substring(0, 8) : 'v1.2';
            provEl.innerText = `${data.provenance.model_name} (${data.provenance.model_version} • SHA: ${shortSum})`;
        }
    }

    // Setup pathology recommendation
    if (meas.total_lesions === 0) {
        document.getElementById('selectPathology').value = "Buồng trứng bình thường (Normal Control)";
    }

    // Update O-RADS indicator
    updateOradsIndicator(document.getElementById('selectPathology').value);
    resetZoomCanvas();
    setCanvasViewMode(currentViewMode);

    // Automatically synthesize structured Clinical NLP narrative & conclusion
    if (typeof autoGenerateAiNarrative === 'function') {
        autoGenerateAiNarrative();
    }

    // Load Background & Mask
    bgImage.onload = () => {
        renderMaskFromRLE(data.rle_mask);
        saveCanvasHistory();
        redrawMainCanvas();
        saveLocalDraft();
    };
    bgImage.src = data.original_image_base64;
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
            if (bgImage.complete && bgImage.naturalWidth > 0) {
                ctx.drawImage(bgImage, 0, 0, 512, 512);
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
            if (origCanvas && splitEditCanvas && bgImage.complete) {
                // Render Original clean viewport
                const oCtx = origCanvas.getContext('2d');
                oCtx.clearRect(0, 0, 512, 512);
                oCtx.drawImage(bgImage, 0, 0, 512, 512);
                drawCalipersOnContext(oCtx);

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
                for (let lesion of currentPrediction.measurements.lesions || []) {
                    if (lesion.caliper_dmax_points && lesion.caliper_dmax_points.length === 2) {
                        const [p1, p2] = lesion.caliper_dmax_points;
                        targetCtx.strokeStyle = '#facc15';
                        targetCtx.lineWidth = 2;
                        targetCtx.beginPath();
                        targetCtx.moveTo(p1[0], p1[1]);
                        targetCtx.lineTo(p2[0], p2[1]);
                        targetCtx.stroke();

                        drawCrosshair(targetCtx, p1[0], p1[1]);
                        drawCrosshair(targetCtx, p2[0], p2[1]);

                        targetCtx.fillStyle = '#facc15';
                        targetCtx.font = 'bold 12px JetBrains Mono';
                        targetCtx.fillText(`D1: ${lesion.max_diameter_mm}mm`, lesion.center[0] - 25, lesion.center[1] - 10);
                    }
                }
            }
        }

function drawCrosshair(c, x, y) {
            c.strokeStyle = '#facc15';
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
                paintOnMask(curX, curY);
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
                        paintOnMask(curX, curY);
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

function paintOnMask(x, y) {
            maskCtx.save();
            if (currentTool === 'brush') {
                maskCtx.fillStyle = 'rgb(6, 182, 212)';
                maskCtx.globalCompositeOperation = 'source-over';
            } else if (currentTool === 'eraser') {
                maskCtx.globalCompositeOperation = 'destination-out';
            }

            maskCtx.beginPath();
            maskCtx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
            maskCtx.fill();
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
