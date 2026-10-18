/** Persisted cases: load the source + stored prediction/review without inference. */
let caseRequest=0, caseFilterTimer, openingCase=false;
function filterCases() {clearTimeout(caseFilterTimer);caseFilterTimer=setTimeout(()=>loadAllCases(),250);}
async function loadAllCases() {
    if(!currentUser||!sessionStorage.getItem('ovarian_ai_access_token')) return;
    const request=++caseRequest;
    const query=new URLSearchParams();
    if($('caseSearch').value.trim()) query.set('search',$('caseSearch').value.trim());
    if($('caseStatusFilter').value!=='ALL') query.set('status',$('caseStatusFilter').value);
    if($('caseDateFilter').value) query.set('date',$('caseDateFilter').value);
    $('casesMessage').textContent='Đang tải các ca đã lưu…';$('casesTableBody').replaceChildren();
    $('casePrev').disabled=$('caseNext').disabled=true;$('caseCount').textContent='';
    try {
        const rows=await apiJson('/api/cases?'+query);
        if(request!==caseRequest) return;
        allCases=rows;currentCasePage=1;renderCaseRows();
        $('casesMessage').textContent=rows.length?'':'Chưa có ca phù hợp. Tạo New Case hoặc thay đổi bộ lọc.';
    } catch(error) {if(request===caseRequest){allCases=[];$('casesMessage').textContent=error.message || 'Không tải được danh sách. Hãy Refresh để thử lại.';}}
}
const thumbCache = new Map();
async function loadThumbnail(img, imageId) {
    if (thumbCache.has(imageId)) {
        img.src = thumbCache.get(imageId);
        return;
    }
    try {
        const data = await apiJson('/api/images/' + encodeURIComponent(imageId) + '/viewer-source');
        if (data?.original_image_base64) {
            thumbCache.set(imageId, data.original_image_base64);
            img.src = data.original_image_base64;
        } else {
            img.replaceWith(createThumbPlaceholder());
        }
    } catch {
        img.replaceWith(createThumbPlaceholder());
    }
}

function createThumbPlaceholder() {
    const el = document.createElement('div');
    el.className = 'thumb-placeholder';
    el.textContent = '🖼';
    return el;
}

function caseTimestamp(value) {
    const match=String(value||'').match(/(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})/);
    return match?Number(match[3]+match[2]+match[1]+match[4]+match[5]):0;
}
function renderCaseRows() {
    const sign=$('caseSort').value==='desc'?-1:1;
    const rows=[...allCases].sort((a,b)=>sign*(caseTimestamp(a.created_at)-caseTimestamp(b.created_at)));
    currentCasePage=Math.min(currentCasePage,Math.max(1,Math.ceil(rows.length/CASE_PAGE_SIZE)));
    const start=(currentCasePage-1)*CASE_PAGE_SIZE;
    $('casesTableBody').replaceChildren();
    for(const item of rows.slice(start,start+CASE_PAGE_SIZE)) {
        const reviewed=item.status==='REVIEWED'||Boolean(item.doctor_action);
        const segmented=['ANALYZED','AI_DONE','REVIEWED'].includes(item.status)||Boolean(item.doctor_action);
        const status=item.status==='PARTIALLY_REVIEWED'?'Partially Reviewed':reviewed?'Confirmed':segmented?'Ready for Review':item.status==='ERROR'?'Error':'Uploaded';
        const tr=document.createElement('tr');
        const codeTd = '<td>'+escapeHtml(item.study_code || item.id)+'</td>';
        const thumbTd = '<td class="thumb-cell"></td>';
        const restTds = '<td><span class="status-badge '+(reviewed?'success':'')+'">'+status+'</span></td><td>'+(segmented?'Completed':'Chưa có kết quả')+'</td><td>'+(reviewed?(item.doctor_action==='MODIFIED'?'Edited & confirmed':item.doctor_action==='REJECTED_ALL'?'Empty mask confirmed':'Confirmed'):'Chờ rà soát')+'</td><td>'+escapeHtml(item.created_at || 'Chưa có dữ liệu')+'</td><td></td>';
        tr.innerHTML = codeTd + thumbTd + restTds;

        const thumbContainer = tr.querySelector('.thumb-cell');
        if (item.image_id) {
            const img = document.createElement('img');
            img.className = 'case-thumb';
            img.alt = 'Ca ' + (item.study_code || item.id);
            img.loading = 'lazy';
            loadThumbnail(img, item.image_id);
            thumbContainer.append(img);
        } else {
            thumbContainer.append(createThumbPlaceholder());
        }

        const button=document.createElement('button');button.className='button';button.textContent='Open →';
        button.addEventListener('click',()=>openCaseInWorkstation(item.id));tr.lastElementChild.append(button);
        $('casesTableBody').append(tr);
    }
    $('caseCount').textContent=rows.length?(start+1)+'–'+Math.min(start+CASE_PAGE_SIZE,rows.length)+' / '+rows.length+' ca trả về · API giới hạn 50 ca mới nhất':'';
    $('casePrev').disabled=currentCasePage<=1;$('caseNext').disabled=start+CASE_PAGE_SIZE>=rows.length;
}
function changeCasePage(delta){currentCasePage+=delta;renderCaseRows();}
async function openCaseInWorkstation(studyId, imageId=null) {
    if(openingCase||!canReplaceCase())return;
    openingCase=true;$('casesMessage').textContent='Đang mở ảnh và mask đã lưu…';
    try {
        const study=await apiJson('/api/cases/'+encodeURIComponent(studyId));
        if(!study.images?.length) {
            $('casesMessage').textContent='Ca chưa có ảnh. Hãy tạo New Case để upload.';
            return;
        }
        if(study.images.length>1&&!imageId) {
            $('caseImageChoices').replaceChildren();
            for(const image of study.images) {
                const button=document.createElement('button');button.className='button';
                button.textContent=(image.filename || image.image_id)+' · '+(image.review?'Confirmed':image.prediction?'Ready for Review':'Uploaded');
                button.onclick=()=>{$('caseImagesModal').close();openCaseInWorkstation(studyId,image.image_id);};
                $('caseImageChoices').append(button);
            }
            $('caseImagesModal').showModal();$('casesMessage').textContent='Chọn ảnh trong ca để tiếp tục.';return;
        }
        const image=imageId?study.images.find(row=>row.image_id===imageId):study.images[0];
        if(!image) throw new Error('Không tìm thấy ảnh trong ca. Hãy mở lại ca.');
        let source=null;
        if(image.prediction) source=await apiJson('/api/images/'+encodeURIComponent(image.image_id)+'/viewer-source');
        resetSingleCase();
        currentCase={study_id:study.study_id,study_code:study.study_code,image_id:image.image_id,image_filename:image.filename,
            patient_id:study.patient_id,ovary_side:study.ovary_side,study_date:study.study_date,clinical_indication:study.clinical_indication,
            sourceDimensions:[image.width,image.height]};
        reflectIntakeMetadata();
        if(!image.prediction) {
            $('uploadCaseId').textContent='Case ID: '+study.study_code;
            $('uploadStatus').textContent='Ảnh đã upload, chưa có kết quả phân đoạn. Có thể thử lại.';
            $('runSegmentationBtn').disabled=false;
            $('runSegmentationBtn').textContent='Retry Segmentation →';
            navigateTo('new_case',{reuseCase:true});
            return;
        }
        currentPrediction={...image.prediction,original_image_base64:source.original_image_base64};
        await initResultsWorkspace(currentPrediction,image.review);
        $('casesMessage').textContent='';navigateTo('results');
    } catch(error) {
        $('casesMessage').textContent=(error.message || 'Không thể mở ca.')+' Hãy tải lại danh sách và thử lại.';
        showToast(error.message || 'Không thể mở ca. Hãy thử lại.',false);
    } finally {openingCase=false;}
}
