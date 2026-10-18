/** Human confirmation is a successful persisted API review, never a local-only badge. */
function encodeCurrentMask() {
    const data=maskCtx.getImageData(0,0,512,512).data, counts=[];
    let value=data[3]>0?1:0,run=0;
    const first=value;
    for(let i=3;i<data.length;i+=4) {
        const next=data[i]>0?1:0;
        if(next===value) run++;
        else {counts.push(run);run=1;value=next;}
    }
    counts.push(run);
    return {shape:[512,512],counts,first_val:first,encoding:'standard_rle'};
}
function sameMask(a,b) {
    return Boolean(a&&b&&(a.first_val||0)===(b.first_val||0)&&a.counts.length===b.counts.length&&a.counts.every((v,i)=>v===b.counts[i]));
}
function getSurveyFeedback() {
    const value=document.querySelector('input[name=hitlRating]:checked')?.value;
    const issues=[...document.querySelectorAll('input[name=hitlIssue]:checked')].map(input=>input.value);
    return value||issues.length ? {usability_rating:value?Number(value):null,issues} : null;
}
function setSurveyFeedback(feedback) {
    document.querySelectorAll('input[name=hitlRating]').forEach(input=>input.checked=input.value===String(feedback?.usability_rating??''));
    document.querySelectorAll('input[name=hitlIssue]').forEach(input=>input.checked=Boolean(feedback?.issues?.includes(input.value)));
}
function changeSurveyIssue(input) {
    if(input.checked) document.querySelectorAll('input[name=hitlIssue]').forEach(other=>{
        if(other!==input&&(input.value==='NO_ERROR'||other.value==='NO_ERROR')) other.checked=false;
    });
}
function markReviewDirty() {
    if(!currentCase.maskReady||currentCase.saving) return;
    const mask=encodeCurrentMask(), notes=$('textDoctorNotes').value.trim();
    const morphology=$('reviewMorphology').value.trim();
    const matchesSaved=currentCase.savedMask&&sameMask(mask,currentCase.savedMask)&&notes===currentCase.savedNotes&&morphology===currentCase.savedMorphology&&JSON.stringify(getSurveyFeedback())===JSON.stringify(currentCase.savedFeedback);
    currentCase.confirmed=Boolean(matchesSaved);
    currentCase.dirty=!matchesSaved && (!sameMask(mask,currentPrediction.rle_mask)||notes.length>0||morphology.length>0||Boolean(getSurveyFeedback())||Boolean(currentCase.review_id));
    currentCase.reviewing=true;
    syncReviewUI();
    if(!sameMask(mask,currentCase.measurementMask)) queueMeasurements();
}
function syncReviewUI() {
    if(!currentPrediction||!currentCase.maskReady) {
        $('confirmSegmentationBtn').disabled=true;$('downloadMaskBtn').disabled=true;$('exportOverlayBtn').disabled=true;$('reportPreviewBtn').disabled=true;return;
    }
    const edited=!sameMask(encodeCurrentMask(),currentPrediction.rle_mask);
    const status=currentCase.confirmed?'Confirmed':edited?'Edited':currentCase.reviewing?'Under Review':'AI Generated';
    $('hudStatus').textContent=status;
    $('hudStatus').className='status-badge'+(currentCase.confirmed?' success':edited?' edited':'');
    $('reviewAI').className='complete';$('reviewHuman').className=currentCase.confirmed?'complete':'current';
    $('reviewConfirmed').className=currentCase.confirmed?'complete':'';
    $('confirmSegmentationBtn').textContent=currentCase.saving?'Saving…':currentCase.confirmed?'Segmentation Confirmed':edited?'Confirm Edited Segmentation':'Confirm Segmentation';
    $('confirmSegmentationBtn').disabled=currentCase.saving||currentCase.confirmed||currentRole!=='DOCTOR';
    $('downloadMaskBtn').disabled=!currentCase.confirmed||currentCase.saving;
    $('exportOverlayBtn').disabled=$('reportPreviewBtn').disabled=!currentCase.confirmed||currentCase.dirty||currentCase.saving;
    $('textDoctorNotes').disabled=Boolean(currentCase.saving);
    $('reviewMorphology').disabled=Boolean(currentCase.saving);
    document.querySelectorAll('.hitl-survey input').forEach(input=>input.disabled=Boolean(currentCase.saving));
    $('resetMaskBtn').disabled=Boolean(currentCase.saving);
    document.querySelectorAll('.tool-buttons button').forEach(button=>button.disabled=Boolean(currentCase.saving));
    $('reviewSavedMessage').textContent=currentCase.saving?'Đang lưu mask & ghi chú…':currentCase.confirmed?'Đã lưu kết quả rà soát vào ca.':currentRole!=='DOCTOR'?'Cần tài khoản người rà soát (DOCTOR) để xác nhận.':'Kết quả hiện tại chưa được xác nhận và lưu.';
    updateHistoryButtons();
}
function openConfirmationModal() {
    if(!currentCase.maskReady||currentCase.saving||currentCase.confirmed||isDrawing) return;
    currentCase.reviewing=true;syncReviewUI();
    const edited=!sameMask(encodeCurrentMask(),currentPrediction.rle_mask);
    $('confirmTitle').textContent=edited?'Confirm Edited Segmentation':'Confirm Segmentation';
    showError('confirmError','');showError('reviewSaveError','');
    $('confirmSignoffModal').showModal();
    $('reviewElapsed').textContent='Thời gian rà soát đến hiện tại: '+Math.max(0,Math.round((performance.now()-reviewStartedAt)/1000))+' giây. Thời gian cuối được ghi khi bấm lưu.';
}
function closeConfirmationModal() {if(!currentCase.saving)$('confirmSignoffModal').close();}
async function executeDoctorSignOff() {
    if(!currentCase.maskReady||currentCase.saving||currentRole!=='DOCTOR') return;
    const rle=encodeCurrentMask();
    const unchanged=sameMask(rle,currentPrediction.rle_mask);
    const empty=rle.first_val===0&&rle.counts.length===1;
    // Preserve ACCEPTED_RAW for an unchanged empty AI mask.
    const action=unchanged?'ACCEPTED_RAW':empty?'REJECTED_ALL':'MODIFIED';
    const notes=$('textDoctorNotes').value.trim();
    currentCase.saving=true;syncReviewUI();
    ['saveReviewBtn','cancelConfirmBtn','closeConfirmBtn'].forEach(id=>$(id).disabled=true);
    $('saveReviewBtn').classList.add('is-loading');$('saveReviewBtn').textContent='Saving…';showError('confirmError','');
    try {
        const review=await apiJson('/api/review',{
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
                study_id:currentCase.study_id,image_id:currentCase.image_id,prediction_id:currentPrediction.prediction_id,
                doctor_id:currentUser.username,doctor_action:action,verified_mask_rle:rle,
                lesion_type:$('reviewMorphology').value.trim()||'Chưa đánh giá bệnh học',clinical_notes:notes,
                hitl_feedback:getSurveyFeedback(),
                time_spent_seconds:reviewStartedAt===null?0:Math.max(1,Math.round((performance.now()-reviewStartedAt)/1000))
            })
        });
        if(!review || typeof review.review_id!=='string' || !review.review_id ||
            review.image_id!==currentCase.image_id || review.status!=='SUCCESS')
            throw new Error('API chưa xác nhận bản Review đã lưu. Hãy mở lại ca để kiểm tra trước khi thử lại.');
        currentCase.review_id=review.review_id;currentCase.savedMask=rle;currentCase.savedNotes=notes;
        currentCase.savedMorphology=$('reviewMorphology').value.trim();currentCase.savedFeedback=getSurveyFeedback();
        currentCase.reviewed_at=review.reviewed_at;
        currentCase.confirmed=true;currentCase.dirty=false;currentCase.doctor_action=action;
        reviewStartedAt=performance.now();
        $('confirmSignoffModal').close();showToast('Đã xác nhận và lưu mask phân đoạn.');
    } catch(error) {
        const message='Save failed. '+(error.message || 'Kiểm tra kết nối và thử lại.')+' Mask chỉnh sửa vẫn được giữ trong workspace.';
        showError('confirmError',message);showError('reviewSaveError',message);
    } finally {
        currentCase.saving=false;
        ['saveReviewBtn','cancelConfirmBtn','closeConfirmBtn'].forEach(id=>$(id).disabled=false);
        $('saveReviewBtn').classList.remove('is-loading');$('saveReviewBtn').textContent='Confirm & Save';syncReviewUI();
    }
}
async function downloadReviewedMask() {
    if(!currentCase.confirmed||!currentCase.image_id) return;
    const button=$('downloadMaskBtn');button.disabled=true;
    try {
        const response=await authenticatedFetch(API_BASE+'/api/images/'+encodeURIComponent(currentCase.image_id)+'/mask.png?kind=reviewed');
        if(!response.ok) throw new Error('Không thể tải mask đã xác nhận. Hãy mở lại ca và thử lại.');
        const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');
        link.href=url;link.download=(currentCase.study_code || 'case')+'-reviewed-mask.png';
        document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    } catch(error) {showToast(error.message || 'Không thể tải mask. Hãy thử lại.',false);}
    finally {syncReviewUI();}
}
