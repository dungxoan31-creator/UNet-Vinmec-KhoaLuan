/** Single-image upload with real request states and retry using the uploaded image. */
let currentSelectedFile=null, previewUrl=null, selectionSerial=0;
function setupDragAndDrop() {
    const zone=$('dropZone');
    ['dragenter','dragover'].forEach(type=>zone.addEventListener(type,e=>{
        e.preventDefault(); if(!currentCase.processing&&!currentCase.selecting) zone.classList.add('drag-over');
    }));
    ['dragleave','drop'].forEach(type=>zone.addEventListener(type,e=>{
        e.preventDefault();zone.classList.remove('drag-over');
    }));
    zone.addEventListener('drop',e=>{
        if(currentCase.processing||currentCase.saving||currentCase.selecting) return;
        if(e.dataTransfer.files.length!==1) return showError('uploadError','Chọn một ảnh siêu âm cho mỗi ca.');
        processUploadedFile(e.dataTransfer.files[0]);
    });
}
function canReplaceCase() {
    if(currentCase.saving||currentCase.processing||currentCase.selecting) {showToast('Đang xử lý. Vui lòng chờ hoàn tất.');return false;}
    return !currentCase.dirty || window.confirm('Mask hoặc ghi chú chưa lưu. Bỏ thay đổi để mở ca khác?');
}
function resetSingleCase({preserveIntake=false}={}) {
    const saved=currentCase.study_id&&preserveIntake ? {
        study_id:currentCase.study_id,study_code:currentCase.study_code,
        patient_id:currentCase.patient_id,ovary_side:currentCase.ovary_side,
        clinical_indication:currentCase.clinical_indication,study_date:currentCase.study_date
    } : {};
    selectionSerial++;
    if(previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl=null;currentSelectedFile=null;currentPrediction=null;currentCase=saved;
    if(typeof clearMeasurements==='function') clearMeasurements();
    maskCtx.clearRect(0,0,512,512);ctx?.clearRect(0,0,512,512);
    bgImage=new Image(); undoStack=[];redoStack=[];reviewStartedAt=null;
    $('fileInput').value='';$('uploadPreview').hidden=true;$('dropZone').hidden=false;
    $('runSegmentationBtn').disabled=true;$('runSegmentationBtn').textContent='Run Segmentation →';
    $('uploadStatus').textContent='Chưa chọn ảnh.';showError('uploadError','');
    $('previewImage').removeAttribute('src');setUploadSteps('');
    if(!preserveIntake) resetIntakeForm();
    syncIntakeControls();
}
function startNewCase() {if(!canReplaceCase())return;resetSingleCase();navigateTo('new_case');}
async function processUploadedFile(file) {
    if(!file||!canReplaceCase()) return false;
    const extension=file.name.split('.').pop().toLowerCase();
    if(!['png','jpg','jpeg','dcm'].includes(extension)) {showError('uploadError','Định dạng không hợp lệ. Chọn PNG, JPG, JPEG hoặc DICOM siêu âm một khung hình.');return false;}
    if(!file.size||file.size>20*1024*1024) {showError('uploadError','Tệp rỗng hoặc vượt quá 20 MB. Hãy chọn ảnh hợp lệ, nhỏ hơn 20 MB.');return false;}
    const session=intakeSession();
    resetSingleCase({preserveIntake:true});
    const serial=selectionSerial, selectedCase=currentCase;
    currentCase.selecting=true;syncIntakeControls();
    currentSelectedFile=file;
    const dicom=extension==='dcm';
    showError('uploadError','');
    $('uploadStatus').textContent='Đang kiểm tra ảnh…';
    $('fileName').textContent=file.name;$('fileMeta').textContent=(file.size/1024).toFixed(0)+' KB';
    $('uploadCaseId').textContent=currentCase.study_id ? 'Case ID: '+(currentCase.study_code||currentCase.study_id) : 'Case ID được cấp khi bắt đầu phân đoạn.';
    $('previewImage').hidden=dicom;$('dicomPreview').hidden=!dicom;
    try {
        if(!dicom) {
            previewUrl=URL.createObjectURL(file);
            const decoded=await loadViewerImage(previewUrl);
            if(serial!==selectionSerial||currentCase!==selectedCase) return false;
            if(!sameIntakeSession(session)) {resetSingleCase();return false;}
            if(decoded.naturalWidth<64||decoded.naturalHeight<64) throw new Error('Ảnh cần có chiều rộng và chiều cao tối thiểu 64 px. Hãy chọn ảnh lớn hơn.');
            $('previewImage').src=previewUrl;
            $('fileMeta').textContent=decoded.naturalWidth+' × '+decoded.naturalHeight+' px · '+(file.size/1024).toFixed(0)+' KB';
        }
        if(serial!==selectionSerial||currentCase!==selectedCase) return false;
        if(!sameIntakeSession(session)) {resetSingleCase();return false;}
        $('uploadPreview').hidden=false;$('dropZone').hidden=true;
        $('runSegmentationBtn').disabled=false;$('uploadStatus').textContent='Ảnh sẵn sàng. Bắt đầu phân đoạn để tạo ca.';
        return true;
    } catch(error) {
        if(serial!==selectionSerial||currentCase!==selectedCase) return false;
        currentSelectedFile=null;$('runSegmentationBtn').disabled=true;
        $('uploadStatus').textContent='Ảnh chưa hợp lệ.';
        showError('uploadError',error.message?.includes('tối thiểu')?error.message:'Không thể đọc ảnh. Chọn ảnh PNG/JPG hợp lệ hoặc DICOM được hỗ trợ.');
        if(previewUrl) URL.revokeObjectURL(previewUrl);previewUrl=null;
        return false;
    } finally {
        if(serial===selectionSerial&&currentCase===selectedCase) {currentCase.selecting=false;syncIntakeControls();}
    }
}
function setUploadSteps(step) {
    document.querySelectorAll('#uploadSteps li').forEach((li,i)=>{
        const index={upload:0,process:1,review:2}[step]??-1;
        li.classList.toggle('done',i<index);
        li.classList.toggle('running',i===index);
    });
}
async function runSingleInference() {
    if(currentCase.processing||currentCase.saving||currentCase.selecting||(!currentSelectedFile&&!currentCase.image_id)) return;
    const session=intakeSession();
    if(!sameIntakeSession(session)) return showError('uploadError','Đăng nhập trước khi tạo ca và tải ảnh.');
    const selectedCase=currentCase, serial=selectionSerial;
    const active=()=>currentCase===selectedCase&&serial===selectionSerial&&sameIntakeSession(session);
    currentCase.processing=true;showError('uploadError','');
    syncIntakeControls();
    $('runSegmentationBtn').classList.add('is-loading');$('runSegmentationBtn').disabled=true;$('fileInput').disabled=true;$('changeImageButton').disabled=true;
    let stage='upload';
    try {
        if(!currentCase.study_id) {
            stage='case';$('uploadStatus').textContent='Đang khởi tạo ca với thông tin tiếp nhận…';
            Object.assign(currentCase,readIntakeMetadata());
            const created=await apiJson('/api/cases',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
                patient_id:currentCase.patient_id,active_ovary_side:currentCase.ovary_side,
                clinical_notes:currentCase.clinical_indication,study_date:currentCase.study_date
            })});
            if(!active()) return;
            if(!created.study_id) throw new Error('API chưa trả về mã ca khám.');
            Object.assign(currentCase,{study_id:created.study_id,study_code:created.study_code,
                patient_id:created.patient_id,ovary_side:created.ovary_side,study_date:created.study_date});
            reflectIntakeMetadata();
            $('uploadCaseId').textContent='Case ID: '+(created.study_code||created.study_id);
        } else if(!currentCase.patient_id||!currentCase.ovary_side||!currentCase.study_date) {
            const detail=await apiJson('/api/cases/'+encodeURIComponent(currentCase.study_id));
            if(!active()) return;
            Object.assign(currentCase,{study_code:detail.study_code,patient_id:detail.patient_id,
                ovary_side:detail.ovary_side,clinical_indication:detail.clinical_indication,study_date:detail.study_date});
            reflectIntakeMetadata();
        }
        if(!currentCase.image_id) {
            stage='upload';
            setUploadSteps('upload');$('uploadStatus').textContent='Đang tải ảnh…';
            const form=new FormData();form.append('file',currentSelectedFile);
            form.append('study_id',currentCase.study_id);
            form.append('anonymized_pid',currentCase.patient_id);
            // Case metadata carries the side; this single image has no bilateral R/L label.
            const uploaded=await apiJson('/api/upload',{method:'POST',body:form});
            if(!active()) return;
            if(uploaded.study_id!==currentCase.study_id||!uploaded.image_id) throw new Error('API tải ảnh trả về mã ca hoặc ảnh không phù hợp.');
            currentCase.image_id=uploaded.image_id;
            currentCase.laterality=uploaded.laterality??null;
            currentCase.image_filename=currentSelectedFile.name;
            currentCase.sourceDimensions=uploaded.dimensions;
            $('uploadCaseId').textContent='Case ID: '+uploaded.study_id;
            if(uploaded.dimensions?.length===2) $('fileMeta').textContent=uploaded.dimensions[0]+' × '+uploaded.dimensions[1]+' px · '+(currentSelectedFile.size/1024).toFixed(0)+' KB';
        }
        stage='process';setUploadSteps('process');
        $('uploadStatus').textContent='Ảnh đã tải lên. Đang tiền xử lý & phân đoạn…';
        $('runSegmentationBtn').textContent='Processing…';
        const data=await apiJson('/api/predict/'+encodeURIComponent(currentCase.image_id),{method:'POST'});
        if(!active()) return;
        currentPrediction=data;
        stage='render';
        await initResultsWorkspace(data);
        if(!active()) return;
        setUploadSteps('review');$('uploadStatus').textContent='Tiền xử lý & phân đoạn hoàn tất. Ready for review.';
        currentCase.processing=false;
        navigateTo('results');
    } catch(error) {
        if(!active()) return;
        $('uploadStatus').textContent=stage==='case'?'Không tạo được ca.':stage==='upload'?'Upload failed.':stage==='render'?'Không thể hiển thị kết quả.':'Segmentation failed.';
        showError('uploadError',(stage==='render' ? 'Ảnh hoặc mask trả về chưa hợp lệ. ' : '')+(error.message || 'Không thể kết nối dịch vụ.')+
            (currentCase.study_id?' Thông tin ca đã lưu. Thử lại tải ảnh/phân đoạn, hoặc chọn New Case để đổi thông tin.':' Hãy kiểm tra thông tin và thử lại.'));
        currentPrediction=null;
    } finally {
        if(currentCase===selectedCase&&serial===selectionSerial) {
            currentCase.processing=false;
            if(!sameIntakeSession(session)) resetSingleCase();
            $('fileInput').disabled=false;$('changeImageButton').disabled=false;
            $('runSegmentationBtn').disabled=!currentSelectedFile&&!currentCase.image_id;
            $('runSegmentationBtn').classList.remove('is-loading');$('runSegmentationBtn').textContent=currentPrediction?'Run Segmentation →':'Retry Segmentation →';
            syncIntakeControls();
        }
    }
}
