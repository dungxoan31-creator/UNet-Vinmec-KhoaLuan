/** Evaluation displays stored backend metrics, independently of the editable case. */
let evalOffset=0, evaluationRequest=0, sampleRequest=0, comparisonRequest=0;
function metricMarkup(name,value) {
    return '<div class="metric"><dt>'+name+'</dt><dd>'+finiteMetric(value)+'</dd></div>';
}
async function loadEvaluation() {
    const request=++evaluationRequest;
    $('evaluationMessage').textContent='Đang tải kết quả đánh giá…';
    $('evaluationSplits').replaceChildren();$('evaluationDetail').hidden=true;
    loadBenchmarkSamples(0);
    try {
        const data=await apiJson('/api/evaluation/metrics');
        if(request!==evaluationRequest) return;
        for(const [key,label] of [['validation','Validation'],['test','Test']]) {
            const split=data[key] || {},card=document.createElement('article');
            card.className='split-card';
            const count=typeof split.count==='number'?split.count+' ảnh':'Chưa có số lượng ảnh';
            card.innerHTML='<header><h2>'+label+'</h2><span>'+escapeHtml(count)+'</span></header><dl class="metrics">'+metricMarkup('Dice',split.dice_mean)+metricMarkup('IoU',split.iou_mean)+metricMarkup('Recall',split.recall_mean)+'</dl>';
            const note=document.createElement('p');
            note.textContent='Checkpoint: '+(split.checkpoint_sha256 || 'API chưa cung cấp')+(key==='test'?(split.patient_level_independence_verified===true?' · API ghi nhận độc lập theo Patient ID.':' · Chưa xác minh độc lập theo Patient ID.'): ' · Kết quả Validation lịch sử.');
            note.className='mono';card.append(note);$('evaluationSplits').append(card);
        }
        $('evaluationMessage').textContent='Nguồn: API đánh giá lưu trữ. Giá trị thiếu được hiển thị “Chưa có”.';
    } catch(error) {if(request===evaluationRequest)$('evaluationMessage').textContent=(error.message || 'Không tải được metrics.')+' Hãy Refresh để thử lại.';}
}
const categoryLabels={EXCELLENT:'Dice ≥ 0.90',GOOD:'0.70 ≤ Dice < 0.90',LOW_DICE:'Dice < 0.70',FALSE_NEGATIVE_DOMINANT:'FN ưu thế',FALSE_POSITIVE_DOMINANT:'FP ưu thế'};
async function loadBenchmarkSamples(offset=0) {
    const request=++sampleRequest;
    offset=Math.max(0,offset);evalOffset=offset;
    $('samplesMessage').textContent='Đang tải các mẫu Validation…';$('evaluationRows').replaceChildren();
    $('evalPrev').disabled=$('evalNext').disabled=true;$('evalPageLabel').textContent='';
    try {
        const query=new URLSearchParams({limit:'20',offset:String(offset),category:$('evalCategory').value});
        const rows=await apiJson('/api/evaluation/samples?'+query);
        if(request!==sampleRequest)return;
        for(const row of rows) {
            const tr=document.createElement('tr');
            tr.innerHTML='<td>'+escapeHtml(row.case_id)+'</td><td>'+finiteMetric(row.dice)+'</td><td>'+finiteMetric(row.iou)+'</td><td>'+finiteMetric(row.recall)+'</td><td>'+escapeHtml(categoryLabels[row.failure_category] || row.failure_category || 'Chưa phân nhóm')+'</td><td></td>';
            const button=document.createElement('button');button.className='button';button.textContent='Compare →';
            button.onclick=()=>openEvaluationCase(row.case_id);tr.lastElementChild.append(button);$('evaluationRows').append(tr);
        }
        $('samplesMessage').textContent=rows.length?'Chỉ các mẫu Validation được API cung cấp.':'Chưa có mẫu phù hợp với bộ lọc.';
        $('evalPageLabel').textContent=rows.length?'Mẫu '+(offset+1)+'–'+(offset+rows.length):'';
        $('evalPrev').disabled=offset===0;$('evalNext').disabled=rows.length<20;
    } catch(error) {if(request===sampleRequest)$('samplesMessage').textContent=(error.message || 'Không tải được mẫu.')+' Hãy Refresh hoặc chọn lại bộ lọc.';}
}
function comparisonFigure(label,source) {
    const figure=document.createElement('figure'),caption=document.createElement('figcaption'),holder=document.createElement('div');
    caption.textContent=label;holder.className='comparison-image';figure.append(caption,holder);
    if(source) {
        const img=new Image();img.alt=label;img.src=source;
        img.onerror=()=>{holder.replaceChildren();const p=document.createElement('p');p.textContent='Không thể hiển thị ảnh này.';holder.append(p);};
        holder.append(img);
    } else {const p=document.createElement('p');p.textContent='Chưa có ảnh từ API';holder.append(p);}
    return figure;
}
async function openEvaluationCase(caseId) {
    const request=++comparisonRequest;
    $('evaluationDetail').hidden=false;$('evaluationDetail').focus();
    $('evaluationCaseTitle').textContent='Validation · '+caseId;
    $('comparisonMessage').textContent='Đang tải ảnh và mask đối chiếu…';
    $('comparisonGrid').replaceChildren();$('evaluationCaseMetrics').replaceChildren();$('evaluationCaseProvenance').textContent='';
    try {
        const data=await apiJson('/api/evaluation/samples/'+encodeURIComponent(caseId)+'/workstation-bundle');
        if(request!==comparisonRequest)return;
        $('comparisonGrid').append(comparisonFigure('Original',data.original_image_base64),comparisonFigure('Ground Truth',data.ground_truth_mask_base64),comparisonFigure('Prediction',data.prediction_mask_base64));
        const overlay=comparisonFigure('Overlay (ảnh gốc)',null);
        $('comparisonGrid').append(overlay);
        if(data.original_image_base64&&data.prediction_mask_base64) {
            try {
                const [image,mask]=await Promise.all([loadViewerImage(data.original_image_base64),loadViewerImage(data.prediction_mask_base64)]);
                if(request!==comparisonRequest)return;
                const nativeCoordinates=mask.naturalWidth===image.naturalWidth&&mask.naturalHeight===image.naturalHeight;
                if(!nativeCoordinates&&(mask.naturalWidth!==512||mask.naturalHeight!==512)) throw new Error('Mask không cùng hệ tọa độ với ảnh.');
                const view=document.createElement('canvas');view.width=view.height=512;view.setAttribute('aria-label','Overlay ảnh gốc và predicted mask');
                const context=view.getContext('2d');context.fillStyle='#000';context.fillRect(0,0,512,512);
                const scale=Math.min(512/image.naturalWidth,512/image.naturalHeight);
                const width=Math.floor(image.naturalWidth*scale),height=Math.floor(image.naturalHeight*scale);
                // Same letterbox geometry as the backend; this visual does not recreate CLAHE.
                context.drawImage(image,Math.floor((512-width)/2),Math.floor((512-height)/2),width,height);
                const colored=document.createElement('canvas');colored.width=mask.naturalWidth;colored.height=mask.naturalHeight;
                const m=colored.getContext('2d');m.drawImage(mask,0,0);
                const pixels=m.getImageData(0,0,colored.width,colored.height);
                for(let i=0;i<pixels.data.length;i+=4) {
                    const foreground=pixels.data[i]>20||pixels.data[i+1]>20||pixels.data[i+2]>20;
                    pixels.data[i]=6;pixels.data[i+1]=182;pixels.data[i+2]=212;pixels.data[i+3]=foreground?255:0;
                }
                m.putImageData(pixels,0,0);context.globalAlpha=.45;
                if(nativeCoordinates) context.drawImage(colored,Math.floor((512-width)/2),Math.floor((512-height)/2),width,height);
                else context.drawImage(colored,0,0);
                context.globalAlpha=1;
                overlay.lastElementChild.replaceChildren(view);
            } catch {overlay.lastElementChild.firstChild.textContent='Không thể căn chỉnh overlay. Xem từng ảnh riêng để đối chiếu.';}
        }
        if(request!==comparisonRequest)return;
        const metrics=data.benchmark_metrics || {};
        if(data.ground_truth_mask_base64) {
            $('evaluationCaseMetrics').innerHTML='<dl>'+metricMarkup('Dice',metrics.dice)+'</dl><dl>'+metricMarkup('IoU',metrics.iou)+'</dl><dl>'+metricMarkup('Recall',metrics.recall)+'</dl>';
            $('comparisonMessage').textContent='Metrics lịch sử từ API, chưa tính lại theo ảnh hiển thị. Overlay dùng ảnh gốc letterbox, không tái tạo CLAHE.';
        } else $('comparisonMessage').textContent='Chưa có ground truth để đối chiếu. Không hiển thị metrics của ca.';
        $('evaluationCaseProvenance').textContent=(data.provenance?.model_name || 'Không có tên model')+' · '+(data.provenance?.dataset_source || 'Nguồn chưa cung cấp')+' · Checkpoint: '+(data.provenance?.checkpoint_sha256 || 'Chưa có');
    } catch(error) {if(request===comparisonRequest)$('comparisonMessage').textContent=(error.message || 'Không tải được ảnh đối chiếu.')+' Chọn lại Compare để thử lại.';}
}
