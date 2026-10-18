/** Canvas edits stay in 512×512 model coordinates; measurements use source coordinates. */
const MAX_HISTORY=20, MAX_ZOOM=5, MIN_ZOOM=.2, ZOOM_STEP=.25;
let imageViewMode='overlay', comparisonMode='single', contourOnly=false, curtainPosition=50;
let brightness=100, contrast=100, measurementSerial=0, measurementTimer, currentMeasurements=null;
function loadViewerImage(src) {
    return new Promise((resolve,reject)=>{
        if(!src) return reject(new Error('Không có ảnh nguồn để hiển thị.'));
        const image=new Image();image.onload=()=>resolve(image);
        image.onerror=()=>reject(new Error('Không thể hiển thị ảnh. Hãy mở lại ca hoặc chọn ảnh khác.'));
        image.src=src;
    });
}

async function initResultsWorkspace(data,review=null) {
    currentCase.maskReady=false; $('viewerLoading').hidden=false; $('editorCanvas').hidden=true;
    ctx.clearRect(0,0,512,512);maskCtx.clearRect(0,0,512,512);
    undoStack=[];redoStack=[];window.groundTruthCanvas=null;reviewStartedAt=performance.now();
    currentCase.confirmed=false;currentCase.dirty=false;
    $('textDoctorNotes').value=review?.clinical_notes||'';
    $('reviewMorphology').value=['UNSPECIFIED','Chưa đánh giá bệnh học'].includes(review?.lesion_type)?'':review?.lesion_type||'';
    setSurveyFeedback(review?.hitl_feedback||null);
    $('viewerStudyCode').textContent=currentCase.study_code||currentCase.study_id||'Case';
    $('viewerFilename').textContent=currentCase.image_filename||data.filename||'';
    $('workstationModelName').textContent=data.provenance?.model_name||data.provenance?.model_version||data.model_version||'Không có thông tin trong bản ghi';
    $('inferenceTime').textContent=typeof data.inference_time_ms==='number'?data.inference_time_ms.toFixed(0)+' ms':'Không có dữ liệu';
    $('modelProvenance').textContent=data.provenance?.model_checksum||data.provenance?.checkpoint_sha256||'Bản ghi chưa cung cấp checksum/version mô hình.';
    $('confidenceInfo').textContent=typeof data.confidence_score==='number'?'Điểm pixel AI (chưa hiệu chuẩn): '+(data.confidence_score*100).toFixed(1)+'%. Không phải độ chính xác lâm sàng.':'Không có confidence từ backend.';
    showError('reviewSaveError','');
    try {
        bgImage=await loadViewerImage(data.original_image_base64);
        dualMaskFromRle(data.rle_mask);renderMaskFromRLE(review?.verified_mask_rle||data.rle_mask);
        undoStack=[maskCtx.getImageData(0,0,512,512)];
        currentCase.maskReady=true;currentCase.confirmed=Boolean(review);currentCase.review_id=review?.review_id||null;
        currentCase.savedMask=review?encodeCurrentMask():null;currentCase.savedNotes=review?.clinical_notes||'';
        currentCase.savedMorphology=$('reviewMorphology').value.trim();
        currentCase.savedFeedback=getSurveyFeedback();currentCase.reviewing=false;
        contourOnly=false;curtainPosition=50;$('curtainSlider').value=50;
        $('contourToggle').setAttribute('aria-pressed','false');
        setComparisonMode('single');setViewMode('overlay');setCanvasTool('brush');resetZoomCanvas();resetImageAdjustments();
        updateHistoryButtons();syncReviewUI();fitCanvasToViewport();queueMeasurements();
        $('reviewPanel').scrollTop=0;document.querySelector('.annotation-tools').scrollTop=0;
    } finally {$('viewerLoading').hidden=true;$('editorCanvas').hidden=!currentCase.maskReady;}
}
function renderMaskFromRLE(rle){const validated=dualMaskFromRle(rle);maskCtx.clearRect(0,0,512,512);maskCtx.drawImage(validated,0,0);}
function drawUltrasound(context) {
    context.fillStyle='#000';context.fillRect(0,0,512,512);
    if(bgImage?.naturalWidth){context.save();context.filter='brightness('+brightness+'%) contrast('+contrast+'%)';context.drawImage(bgImage,0,0,512,512);context.restore();}
}
function outlineMask() {
    const source=maskCtx.getImageData(0,0,512,512).data;
    const result=ctx.createImageData(512,512);
    for(let y=0;y<512;y++)for(let x=0;x<512;x++){
        const i=(y*512+x)*4;
        if(source[i+3]&&(x===0||y===0||x===511||y===511||!source[i-1]||!source[i+7]||!source[i-2045]||!source[i+2051])){
            result.data[i]=6;result.data[i+1]=182;result.data[i+2]=212;result.data[i+3]=255;
        }
    }
    const outline=document.createElement('canvas');outline.width=outline.height=512;outline.getContext('2d').putImageData(result,0,0);return outline;
}
function redrawMainCanvas() {
    if(!ctx)return;
    ctx.clearRect(0,0,512,512);
    if(imageViewMode==='mask'&&comparisonMode==='single'){
        const binary=maskCtx.getImageData(0,0,512,512);
        for(let i=0;i<binary.data.length;i+=4){const v=binary.data[i+3]>0?255:0;binary.data[i]=binary.data[i+1]=binary.data[i+2]=v;binary.data[i+3]=255;}
        ctx.putImageData(binary,0,0);
    }else{
        drawUltrasound(ctx);
        if(imageViewMode!=='original'||comparisonMode!=='single'){
            ctx.save();
            if(comparisonMode==='curtain'){ctx.beginPath();ctx.rect(512*curtainPosition/100,0,512,512);ctx.clip();}
            ctx.globalAlpha=contourOnly?1:maskOpacity;ctx.drawImage(contourOnly?outlineMask():maskCanvas,0,0);ctx.restore();
            if(currentMeasurements&&maskOpacity>0&&comparisonMode!=='curtain'){
                ctx.save();ctx.strokeStyle='#efc867';ctx.lineWidth=1.5;
                for(const lesion of currentMeasurements.lesions||[])for(const points of [lesion.viewer_caliper_dmax_points,lesion.viewer_caliper_dorth_points]){
                    if(!points?.length)continue;ctx.beginPath();ctx.moveTo(...points[0]);ctx.lineTo(...points[1]);ctx.stroke();
                }
                ctx.restore();
            }
        }
        if(comparisonMode==='curtain'){ctx.save();ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(512*curtainPosition/100,0);ctx.lineTo(512*curtainPosition/100,512);ctx.stroke();ctx.restore();}
    }
    const original=$('comparisonOriginalCanvas');
    if(original&&comparisonMode==='side')drawUltrasound(original.getContext('2d'));
    positionCurtainHandle();
    if(isCalibratingTwoPoints||(calibPoints&&calibPoints.length>0)){
        ctx.save();ctx.strokeStyle='#22c55e';ctx.fillStyle='#22c55e';ctx.lineWidth=2;
        for(const p of calibPoints){
            ctx.beginPath();ctx.arc(p[0],p[1],4,0,Math.PI*2);ctx.fill();
            ctx.beginPath();ctx.moveTo(p[0]-8,p[1]);ctx.lineTo(p[0]+8,p[1]);
            ctx.moveTo(p[0],p[1]-8);ctx.lineTo(p[0],p[1]+8);ctx.stroke();
        }
        if(calibPoints.length===2){
            ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(calibPoints[0][0],calibPoints[0][1]);ctx.lineTo(calibPoints[1][0],calibPoints[1][1]);ctx.stroke();
        }
        ctx.restore();
    }
}
function setViewMode(mode) {
    imageViewMode=mode;
    if(comparisonMode!=='single'&&mode!=='overlay')setComparisonMode('single');
    document.querySelectorAll('[data-view]').forEach(b=>{const active=b.dataset.view===mode;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
    $('opacitySlider').disabled=mode!=='overlay'||contourOnly;redrawMainCanvas();
}
function setComparisonMode(mode) {
    comparisonMode=mode;
    $('canvasContainer').classList.toggle('side-by-side',mode==='side');
    $('originalPane').hidden=mode!=='side';$('editablePaneLabel').hidden=mode!=='side';
    $('curtainControl').hidden=mode!=='curtain';
    document.querySelectorAll('[data-comparison]').forEach(b=>{const active=b.dataset.comparison===mode;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
    if(mode!=='single')setViewMode('overlay');else redrawMainCanvas();
    $('brushCursor').hidden=true;applyCanvasZoom();requestAnimationFrame(positionCurtainHandle);
}
function toggleContour(){contourOnly=!contourOnly;$('contourToggle').setAttribute('aria-pressed',String(contourOnly));$('contourToggle').textContent=contourOnly?'Mặt nạ phủ màu':'Đường viền';$('opacitySlider').disabled=contourOnly||imageViewMode!=='overlay';redrawMainCanvas();}
function updateCurtain(value){curtainPosition=Math.max(0,Math.min(100,Number(value)));$('curtainSlider').value=curtainPosition;redrawMainCanvas();}
function updateImageAdjustments(){brightness=Number($('brightnessSlider').value);contrast=Number($('contrastSlider').value);$('brightnessValue').value=brightness+'%';$('contrastValue').value=contrast+'%';redrawMainCanvas();}
function resetImageAdjustments(){$('brightnessSlider').value=$('contrastSlider').value=100;updateImageAdjustments();}
function updateOverlayOpacity(value){maskOpacity=Number(value)/100;$('opacityValue').value=value+'%';redrawMainCanvas();}
function applyCanvasZoom() {
    if(!canvas)return;
    const transform='translate('+panOffsetX+'px,'+panOffsetY+'px) scale('+currentZoom+')';
    canvas.style.transform=transform;$('comparisonOriginalCanvas').style.transform=transform;
    $('zoomLevelDisplay').textContent=Math.round(currentZoom*100)+'%';$('brushCursor').hidden=true;positionCurtainHandle();
}
function zoomAtPoint(deltaZoom, clientX, clientY) {
    if(!canvas||!currentCase.maskReady) return;
    const oldZoom=currentZoom;
    const newZoom=Math.max(MIN_ZOOM,Math.min(MAX_ZOOM,Math.round((currentZoom+deltaZoom)*100)/100));
    if(newZoom===oldZoom) return;
    const container=$('canvasContainer');
    const r=container.getBoundingClientRect();
    const cx=clientX-r.left-r.width/2;
    const cy=clientY-r.top-r.height/2;
    const scaleRatio=newZoom/oldZoom;
    panOffsetX=Math.round(cx-(cx-panOffsetX)*scaleRatio);
    panOffsetY=Math.round(cy-(cy-panOffsetY)*scaleRatio);
    currentZoom=newZoom;
    applyCanvasZoom();
}
function zoomInCanvas(){if(!canvas)return;const r=$('canvasContainer').getBoundingClientRect();zoomAtPoint(ZOOM_STEP,r.left+r.width/2,r.top+r.height/2);}
function zoomOutCanvas(){if(!canvas)return;const r=$('canvasContainer').getBoundingClientRect();zoomAtPoint(-ZOOM_STEP,r.left+r.width/2,r.top+r.height/2);}
function resetZoomCanvas(){currentZoom=1;panOffsetX=panOffsetY=0;applyCanvasZoom();}
function setBrushSize(value){brushSize=Math.max(2,Math.min(64,Number(value)));$('brushSizeSlider').value=brushSize;$('brushSizeValue').value=brushSize+' px';$('brushCursor').hidden=true;}
function setCanvasTool(tool) {
    currentTool=tool;
    for(const name of ['brush','eraser','pan']){const b=$('tool'+name[0].toUpperCase()+name.slice(1));b.classList.toggle('active',name===tool);b.setAttribute('aria-pressed',String(name===tool));}
    if(canvas)canvas.style.cursor=tool==='pan'?'grab':'none';$('brushCursor').hidden=true;
}
function showBrushCursor(event) {
    const ring=$('brushCursor');
    if(currentTool==='pan'||event.shiftKey||!currentCase.maskReady||currentCase.saving){ring.hidden=true;return;}
    const imageRect=canvas.getBoundingClientRect(),paneRect=$('editablePane').getBoundingClientRect();
    const size=brushSize*imageRect.width/512;
    ring.style.width=ring.style.height=size+'px';ring.style.left=(event.clientX-paneRect.left)+'px';ring.style.top=(event.clientY-paneRect.top)+'px';ring.hidden=false;
    ring.classList.toggle('eraser',currentTool==='eraser');
}
function positionCurtainHandle(){
    const handle=$('curtainHandle');if(!handle||!canvas)return;
    handle.hidden=comparisonMode!=='curtain';if(handle.hidden)return;
    const rect=canvas.getBoundingClientRect(),pane=$('editablePane').getBoundingClientRect();
    handle.style.left=(rect.left-pane.left+rect.width*curtainPosition/100)+'px';handle.style.top=(rect.top-pane.top)+'px';handle.style.height=rect.height+'px';
    handle.setAttribute('aria-valuenow',String(Math.round(curtainPosition)));
}
function fitCanvasToViewport(){
    if(!canvas)return;
    const pane=$('editablePane'),dims=currentCase.sourceDimensions;
    let contentWidth=512,contentHeight=512;
    if(Array.isArray(dims)&&dims.length===2&&dims.every(n=>Number.isFinite(n)&&n>0)){
        const scale=Math.min(512/dims[0],512/dims[1]);
        contentWidth=Math.max(1,Math.floor(dims[0]*scale));contentHeight=Math.max(1,Math.floor(dims[1]*scale));
    }
    // Fit the image content, allowing only letterbox padding to be clipped.
    const size=Math.max(1,Math.min(512,pane.clientWidth*512/contentWidth,(pane.clientHeight||512)*512/contentHeight));
    for(const item of [canvas,$('comparisonOriginalCanvas')])item.style.width=item.style.height=size+'px';
    positionCurtainHandle();$('brushCursor').hidden=true;
}
function setupCanvasEngine() {
    canvas=$('editorCanvas');ctx=canvas.getContext('2d');
    const point=e=>{const r=canvas.getBoundingClientRect();return[(e.clientX-r.left)*512/r.width,(e.clientY-r.top)*512/r.height];};
    const handle=document.createElement('div');handle.id='curtainHandle';handle.className='curtain-handle';handle.hidden=true;handle.tabIndex=0;
    handle.setAttribute('role','slider');handle.setAttribute('aria-label','Ranh giới ảnh gốc và mask');handle.setAttribute('aria-valuemin','0');handle.setAttribute('aria-valuemax','100');
    $('editablePane').append(handle);
    let draggingCurtain=false;
    handle.addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();draggingCurtain=true;handle.setPointerCapture(e.pointerId);$('brushCursor').hidden=true;});
    handle.addEventListener('pointermove',e=>{if(draggingCurtain){const r=canvas.getBoundingClientRect();updateCurtain((e.clientX-r.left)*100/r.width);}});
    ['pointerup','pointercancel','lostpointercapture'].forEach(type=>handle.addEventListener(type,()=>draggingCurtain=false));
    handle.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();e.stopPropagation();updateCurtain(e.key==='Home'?0:e.key==='End'?100:curtainPosition+(e.key==='ArrowLeft'?-2:2));}});
    canvas.addEventListener('pointerdown',e=>{
        if(!currentCase.maskReady||currentCase.saving||document.querySelector('dialog[open]'))return;
        const isPanTrigger=(e.button===1||e.button===2||currentTool==='pan'||e.shiftKey||isSpacePressed);
        if(!isPanTrigger&&e.button!==0)return;
        e.preventDefault();canvas.setPointerCapture(e.pointerId);
        if(isPanTrigger){isPanning=true;startPanX=e.clientX-panOffsetX;startPanY=e.clientY-panOffsetY;canvas.style.cursor='grabbing';return;}
        if(isCalibratingTwoPoints){handleCalibrationClick(e);return;}
        if(imageViewMode==='original')setViewMode('overlay');
        const initialPoint=point(e);
        clearMeasurements('Mask đang chỉnh sửa; chờ tính lại số đo.');
        [lastX,lastY]=initialPoint;isDrawing=true;paintOnMask(lastX,lastY);currentCase.reviewing=true;currentCase.confirmed=false;syncReviewUI();
    });
    canvas.addEventListener('pointermove',e=>{
        showBrushCursor(e);
        if(isPanning){panOffsetX=e.clientX-startPanX;panOffsetY=e.clientY-startPanY;applyCanvasZoom();return;}
        if(!isDrawing)return;const[x,y]=point(e);paintOnMask(x,y,lastX,lastY);lastX=x;lastY=y;
    });
    canvas.addEventListener('pointerleave',()=>{$('brushCursor').hidden=true;});
    const finish=()=>{if(isDrawing){isDrawing=false;saveCanvasHistory();markReviewDirty();}isPanning=false;canvas.style.cursor=currentTool==='pan'?'grab':'none';};
    ['pointerup','pointercancel','lostpointercapture'].forEach(type=>canvas.addEventListener(type,finish));
    const original=$('comparisonOriginalCanvas');
    original.addEventListener('pointerdown',e=>{if(e.button!==0||!currentCase.maskReady)return;e.preventDefault();original.setPointerCapture(e.pointerId);isPanning=true;startPanX=e.clientX-panOffsetX;startPanY=e.clientY-panOffsetY;});
    original.addEventListener('pointermove',e=>{if(isPanning){panOffsetX=e.clientX-startPanX;panOffsetY=e.clientY-startPanY;applyCanvasZoom();}});
    ['pointerup','pointercancel','lostpointercapture'].forEach(type=>original.addEventListener(type,()=>{isPanning=false;}));
    canvas.addEventListener('contextmenu',e=>e.preventDefault());
    original.addEventListener('contextmenu',e=>e.preventDefault());
    $('canvasContainer').addEventListener('wheel',e=>{if(!currentCase.maskReady)return;e.preventDefault();const delta=e.deltaY<0?ZOOM_STEP:-ZOOM_STEP;zoomAtPoint(delta,e.clientX,e.clientY);},{passive:false});
    new ResizeObserver(fitCanvasToViewport).observe($('editablePane'));
    let resizeTimer;
    window.addEventListener('resize',()=>{
        clearTimeout(resizeTimer);
        resizeTimer=setTimeout(()=>{fitCanvasToViewport();applyCanvasZoom();},150);
    });
}
function paintOnMask(x,y,prevX=null,prevY=null) {
    maskCtx.save();maskCtx.lineCap='round';maskCtx.lineJoin='round';maskCtx.lineWidth=brushSize;
    maskCtx.strokeStyle=maskCtx.fillStyle='rgb(6,182,212)';maskCtx.globalCompositeOperation=currentTool==='eraser'?'destination-out':'source-over';
    if(typeof prevX==='number'){maskCtx.beginPath();maskCtx.moveTo(prevX,prevY);maskCtx.lineTo(x,y);maskCtx.stroke();}
    else{maskCtx.beginPath();maskCtx.arc(x,y,brushSize/2,0,Math.PI*2);maskCtx.fill();}
    maskCtx.restore();redrawMainCanvas();
}
function clearMeasurements(message='Chưa có số đo.'){
    currentCase.measurementMask=null;
    ++measurementSerial;clearTimeout(measurementTimer);currentMeasurements=null;
    for(const id of ['measurementDmax','measurementDortho','measurementArea'])$(id).textContent='—';
    $('calibrationBadge').textContent='Chưa có số đo';$('calibrationBadge').className='status-badge';$('measurementStatus').textContent=message;
}
function updateMeasurementDisplay() {
    if (!currentMeasurements) return;
    const m = currentMeasurements;
    const manualSpacing = currentCase.manualSpacingMm;
    const isCalibrated = m.calibrated || Boolean(manualSpacing && manualSpacing > 0);
    const spacing = m.calibrated ? m.pixel_spacing_mm : (manualSpacing || null);

    if (isCalibrated && spacing) {
        const dmax = m.calibrated && m.max_diameter_mm !== null ? m.max_diameter_mm : (m.max_diameter_px * spacing);
        const dorth = m.calibrated && m.ortho_diameter_mm !== null ? m.ortho_diameter_mm : (m.ortho_diameter_px * spacing);
        const area = m.calibrated && m.total_area_cm2 !== null ? m.total_area_cm2 : (m.total_area_px * spacing * spacing / 100);

        $('measurementDmax').textContent = dmax.toFixed(1) + ' mm';
        $('measurementDortho').textContent = dorth.toFixed(1) + ' mm';
        $('measurementArea').textContent = area.toFixed(2) + ' cm²';
        $('calibrationBadge').textContent = m.calibrated ? (m.calibration_source === 'DICOM' ? 'Hiệu chuẩn DICOM' : 'Đã hiệu chuẩn mm') : `Thủ công: ${(1/spacing).toFixed(1)} px/mm`;
        $('calibrationBadge').className = 'status-badge success';
        $('measurementStatus').textContent = `Độ phân giải: 1 px ≈ ${spacing.toFixed(4)} mm`;
    } else {
        $('measurementDmax').textContent = (m.max_diameter_px || 0).toFixed(1) + ' px';
        $('measurementDortho').textContent = (m.ortho_diameter_px || 0).toFixed(1) + ' px';
        $('measurementArea').textContent = Math.round(m.total_area_px || 0) + ' px²';
        $('calibrationBadge').textContent = 'Chưa hiệu chuẩn (pixel)';
        $('calibrationBadge').className = 'status-badge';
        $('measurementStatus').textContent = 'Số đo hiển thị đơn vị pixel trên ảnh nguồn. Nhấn "Hiệu chuẩn thước" để đổi sang mm.';
    }
}
function queueMeasurements(){
    if(!currentCase.maskReady||!currentCase.image_id)return;
    const id=currentCase.image_id,rle=encodeCurrentMask();
    clearMeasurements('Đang tính số đo trên mask hiện tại…');const serial=measurementSerial;currentCase.measurementMask=rle;
    redrawMainCanvas();
    measurementTimer=setTimeout(async()=>{
        try{
            const m=await apiJson('/api/images/'+encodeURIComponent(id)+'/measurements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rle_mask:rle})});
            if(serial!==measurementSerial||id!==currentCase.image_id||!sameMask(rle,encodeCurrentMask()))return;
            currentMeasurements=m;
            currentCase.sourceDimensions=m.source_dimensions;fitCanvasToViewport();
            updateMeasurementDisplay();
            redrawMainCanvas();
        }catch(error){if(serial===measurementSerial){clearMeasurements('Không lấy được số đo. '+error.message);redrawMainCanvas();}}
    },180);
}
// Existing two-image engine retained for historical integrations; not mounted in the primary UI.
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
        if (!document.getElementById('screenDualResults')?.classList?.contains('active')) return;
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
            ? `${metrics.max_diameter_mm.toFixed(1)} × ${metrics.ortho_diameter_mm.toFixed(1)}` : 'Chưa hiệu chuẩn';
        document.getElementById(`dualVolume${side}`).textContent = 'Không đo từ ảnh 2D';
        document.getElementById(`dualConfidence${side}`).textContent = Number.isFinite(prediction.confidence_score)
            ? `${(prediction.confidence_score * 100).toFixed(1)}% (chưa hiệu chuẩn)` : '—';
        document.getElementById(`dualClinical${side}`).textContent = 'Chờ đánh giá chuyên môn';
    }
}

async function downloadDualMask(side) {
    const item = dualCase.sides[side];
    if (!item || !item.imageId) {
        showToast('Chưa có ảnh để xuất mask.', false);
        return;
    }
    if (!item.approved) {
        showToast('Hãy xác nhận và lưu mask trước khi tải.', false);
        return;
    }
    const kind = 'reviewed';
    try {
        const response = await authenticatedFetch(`${API_BASE}/api/images/${encodeURIComponent(item.imageId)}/mask.png?kind=${kind}`);
        if (!response.ok) throw new Error('Chưa có mask đã lưu.');
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a');
        link.href = url;
        link.download = `${item.imageId}_${kind}_mask.png`;
        link.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        showToast(error.message, false);
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


function updateHistoryButtons() {
    $('undoBtn').disabled=currentCase.saving||undoStack.length<2;
    $('redoBtn').disabled=currentCase.saving||redoStack.length===0;
}
function saveCanvasHistory() {
    undoStack.push(maskCtx.getImageData(0,0,512,512));
    if(undoStack.length>MAX_HISTORY) undoStack.shift();
    redoStack=[]; updateHistoryButtons();
}
function undoCanvas() {
    if(currentCase.saving||isDrawing||undoStack.length<2) return;
    redoStack.push(undoStack.pop());maskCtx.putImageData(undoStack[undoStack.length-1],0,0);
    redrawMainCanvas();markReviewDirty();updateHistoryButtons();
}
function redoCanvas() {
    if(currentCase.saving||isDrawing||!redoStack.length) return;
    const next=redoStack.pop();undoStack.push(next);maskCtx.putImageData(next,0,0);
    redrawMainCanvas();markReviewDirty();updateHistoryButtons();
}
function resetMaskToAI() {
    if(!currentCase.maskReady||currentCase.saving||isDrawing) return;
    renderMaskFromRLE(currentPrediction.rle_mask);saveCanvasHistory();redrawMainCanvas();markReviewDirty();
    showToast('Đã khôi phục mask AI. Có thể Undo để trở lại bản chỉnh sửa.');
}

/* PACS Ergonomics & Modal Controllers */
function openShortcutModal() {
    const el = $('shortcutModal');
    if (el && !el.open) el.showModal();
}
function closeShortcutModal() {
    const el = $('shortcutModal');
    if (el && el.open) el.close();
}

function toggleToolsSidebar() {
    const ws = $('workstation');
    if (!ws) return;
    toolsSidebarCollapsed = !toolsSidebarCollapsed;
    ws.classList.toggle('tools-collapsed', toolsSidebarCollapsed);
    const btn = $('toggleToolsBtn');
    if (btn) btn.textContent = toolsSidebarCollapsed ? '▶' : '◀';
}

function toggleReviewSidebar() {
    const ws = $('workstation');
    if (!ws) return;
    reviewSidebarCollapsed = !reviewSidebarCollapsed;
    ws.classList.toggle('review-collapsed', reviewSidebarCollapsed);
    const btn = $('toggleReviewBtn');
    if (btn) btn.textContent = reviewSidebarCollapsed ? '◀' : '▶';
}

function openCalibrationModal() {
    const el = $('calibrationModal');
    if (el && !el.open) {
        el.showModal();
        updateCalibRatioPreview();
    }
}
function closeCalibrationModal() {
    const el = $('calibrationModal');
    if (el && el.open) el.close();
    isCalibratingTwoPoints = false;
    const inst = $('calibInstruction');
    if (inst) inst.hidden = true;
    const btn = $('start2PointCalibBtn');
    if (btn) btn.textContent = '📍 Bắt đầu chấm 2 điểm trên ảnh';
    redrawMainCanvas();
}
function startTwoPointCalibration() {
    closeCalibrationModal();
    isCalibratingTwoPoints = true;
    calibPoints = [];
    showToast('Nhấp điểm 1, sau đó nhấp điểm 2 trên vạch thước ảnh siêu âm.');
}
function updateCalibRatioPreview() {
    const pxInput = $('calibPxDist');
    const mmInput = $('calibMmDist');
    const textEl = $('calibResultRatio');
    if (!pxInput || !mmInput || !textEl) return;
    const px = parseFloat(pxInput.value);
    const mm = parseFloat(mmInput.value);
    if (px > 0 && mm > 0) {
        const ratio = mm / px;
        textEl.textContent = `Tỷ lệ: 1 px ≈ ${ratio.toFixed(4)} mm (${(px/mm).toFixed(2)} px/mm)`;
    } else {
        textEl.textContent = 'Tỷ lệ: Chưa xác định';
    }
}
function applyManualCalibration() {
    const pxInput = $('calibPxDist');
    const mmInput = $('calibMmDist');
    if (!pxInput || !mmInput) return;
    const px = parseFloat(pxInput.value);
    const mm = parseFloat(mmInput.value);
    if (!px || px <= 0 || !mm || mm <= 0) {
        showToast('Vui lòng nhập khoảng cách pixel và mm hợp lệ.', false);
        return;
    }
    const ratio = mm / px;
    currentCase.manualSpacingMm = ratio;
    const badge = $('calibrationBadge');
    if (badge) {
        badge.textContent = `Thủ công: ${(px/mm).toFixed(1)} px/mm`;
        badge.className = 'status-badge success';
    }
    closeCalibrationModal();
    showToast(`Đã áp dụng hiệu chuẩn tỷ lệ: 1 px = ${ratio.toFixed(4)} mm`);
    queueMeasurements();
}
function resetManualCalibration() {
    currentCase.manualSpacingMm = null;
    calibPoints = [];
    const pxInput = $('calibPxDist');
    const mmInput = $('calibMmDist');
    if (pxInput) pxInput.value = '';
    if (mmInput) mmInput.value = '10';
    const badge = $('calibrationBadge');
    if (badge) {
        badge.textContent = 'Chưa hiệu chuẩn';
        badge.className = 'status-badge';
    }
    closeCalibrationModal();
    showToast('Đã xóa hiệu chuẩn thủ công.');
    queueMeasurements();
}
function handleCalibrationClick(e) {
    if (!canvas) return;
    const r = canvas.getBoundingClientRect();
    const x = (e.clientX - r.left) * 512 / r.width;
    const y = (e.clientY - r.top) * 512 / r.height;
    calibPoints.push([x, y]);
    redrawMainCanvas();
    if (calibPoints.length === 2) {
        const dx = calibPoints[1][0] - calibPoints[0][0];
        const dy = calibPoints[1][1] - calibPoints[0][1];
        const distPx = Math.sqrt(dx * dx + dy * dy);
        const pxInput = $('calibPxDist');
        if (pxInput) pxInput.value = distPx.toFixed(1);
        updateCalibRatioPreview();
        isCalibratingTwoPoints = false;
        openCalibrationModal();
        showToast(`Đã ghi nhận 2 điểm (${distPx.toFixed(1)} px). Nhập số mm tương ứng để hoàn tất.`);
    }
}
