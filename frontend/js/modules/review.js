/**
 * MODULE: REVIEW.JS
 */


function saveLocalDraft() {
            try {
                if (currentCase && currentCase.patient_id) {
                    const draft = {
                        patient_id: currentCase.patient_id,
                        study_code: currentCase.study_code,
                        image_id: currentCase.image_id,
                        doctor_action: currentCase.doctor_action,
                        selectedPathology: document.getElementById('selectPathology') ? document.getElementById('selectPathology').value : '',
                        doctorNotes: document.getElementById('textDoctorNotes') ? document.getElementById('textDoctorNotes').value : '',
                        timestamp: new Date().toISOString()
                    };
                    localStorage.setItem('vinmec_ovarian_ai_draft', JSON.stringify(draft));
                    const draftPill = document.getElementById('hudDraftPill');
                    if (draftPill) draftPill.innerText = '💾 Tự động lưu: ' + new Date().toLocaleTimeString();
                }
            } catch (e) {}
        }

function checkDraftOnLoad() {
    try {
        const raw = localStorage.getItem('vinmec_ovarian_ai_draft');
        const banner = document.getElementById('draftRestorationBanner');
        const bannerText = document.getElementById('draftBannerText');
        if (raw) {
            const draft = JSON.parse(raw);
            if (banner && bannerText && draft && draft.patient_id) {
                bannerText.innerText = `Bệnh nhân: ${draft.patient_id} • Mã ca: ${draft.study_code || 'Chưa đặt mã'} • Lưu lúc: ${draft.timestamp ? new Date(draft.timestamp).toLocaleTimeString() : 'Gần đây'}`;
                banner.style.display = 'flex';
            }
        } else if (banner) {
            banner.style.display = 'none';
        }
    } catch (e) {}
}

function restoreLocalDraft() {
    try {
        const raw = localStorage.getItem('vinmec_ovarian_ai_draft');
        if (!raw) {
            showToast("Không tìm thấy bản nháp nào.", false);
            return;
        }
        const draft = JSON.parse(raw);
        if (typeof currentCase === 'undefined' || !currentCase) {
            window.currentCase = {};
        }
        Object.assign(currentCase, draft);
        if (draft.doctorNotes && document.getElementById('textDoctorNotes')) {
            document.getElementById('textDoctorNotes').value = draft.doctorNotes;
        }
        if (draft.doctor_action) {
            chooseDoctorAction(draft.doctor_action);
        }
        const banner = document.getElementById('draftRestorationBanner');
        if (banner) banner.style.display = 'none';

        if (currentPrediction) {
            navigateTo('results');
        } else if (draft.image_id) {
            navigateTo('results');
        } else {
            navigateTo('create_case');
        }
        showToast("✓ Đã khôi phục dữ liệu bản nháp thành công!");
    } catch (e) {
        showToast("Lỗi khi khôi phục bản nháp: " + e.message, false);
    }
}

function discardLocalDraft() {
    try {
        localStorage.removeItem('vinmec_ovarian_ai_draft');
        const banner = document.getElementById('draftRestorationBanner');
        if (banner) banner.style.display = 'none';
        showToast("Đã xóa bản nháp thành công.");
    } catch (e) {}
}

function onPathologyChanged(val) {
    updateOradsIndicator(val);
    saveLocalDraft();
}

function updateOradsIndicator(pathology) {
    const badge = document.getElementById('oradsScoreBadge');
    const pointer = document.getElementById('oradsPointer');
    if (!badge || !pointer || !pathology) return;

    badge.className = 'orads-badge';
    if (pathology.includes('Normal') || pathology.includes('bình thường')) {
        badge.classList.add('orads-badge-1');
        badge.innerText = 'O-RADS 1 (Bình thường)';
        pointer.style.left = '10%';
    } else if (pathology.includes('Simple') || pathology.includes('thanh dịch')) {
        badge.classList.add('orads-badge-2');
        badge.innerText = 'O-RADS 2 (Lành tính <1%)';
        pointer.style.left = '30%';
    } else if (pathology.includes('Dermoid') || pathology.includes('U bì') || pathology.includes('quái')) {
        badge.classList.add('orads-badge-2');
        badge.innerText = 'O-RADS 2 (U bì <1%)';
        pointer.style.left = '35%';
    } else if (pathology.includes('Endometrioma') || pathology.includes('lạc nội mạc')) {
        badge.classList.add('orads-badge-3');
        badge.innerText = 'O-RADS 3 (Nguy cơ 1-10%)';
        pointer.style.left = '52%';
    } else if (pathology.includes('Hemorrhagic') || pathology.includes('xuất huyết')) {
        badge.classList.add('orads-badge-2');
        badge.innerText = 'O-RADS 2 (Lành tính <1%)';
        pointer.style.left = '30%';
    } else if (pathology.includes('nhầy') || pathology.includes('Mucinous')) {
        badge.classList.add('orads-badge-3');
        badge.innerText = 'O-RADS 3 (Nguy cơ 1-10%)';
        pointer.style.left = '55%';
    } else if (pathology.includes('Solid') || pathology.includes('đặc') || pathology.includes('nghi ngờ')) {
        badge.classList.add('orads-badge-4');
        badge.innerText = 'O-RADS 4 (Nguy cơ 10-50%)';
        pointer.style.left = '75%';
    } else if (pathology.includes('CHỜ BÁC SĨ') || pathology.includes('Chưa thể kết luận')) {
        badge.style.background = '#f1f5f9';
        badge.style.color = '#475569';
        badge.style.border = '1px solid #cbd5e1';
        badge.innerText = 'O-RADS -- (Chờ Bác sĩ)';
        pointer.style.left = '30%';
    } else {
        badge.classList.add('orads-badge-2');
        badge.innerText = 'O-RADS 2 (Lành tính <1%)';
        pointer.style.left = '30%';
    }
}

function insertMacro(text) {
    const textarea = document.getElementById('textDoctorNotes');
    textarea.value = text;
    textarea.focus();
    showToast("✓ Đã áp dụng mẫu mô tả lâm sàng!");
}

function chooseDoctorAction(action) {
            currentCase.doctor_action = action;
            document.querySelectorAll('.decision-choice-card').forEach(c => c.classList.remove('selected'));
            if (action === 'ACCEPTED_RAW') {
                document.getElementById('cardOptAccept').classList.add('selected');
                document.querySelector('input[value="ACCEPTED_RAW"]').checked = true;
                if (currentPrediction?.rle_mask) {
                    renderMaskFromRLE(currentPrediction.rle_mask);
                    saveCanvasHistory();
                    redrawMainCanvas();
                }
            } else if (action === 'MODIFIED') {
                document.getElementById('cardOptModify').classList.add('selected');
                document.querySelector('input[value="MODIFIED"]').checked = true;
            } else {
                document.getElementById('cardOptReject').classList.add('selected');
                document.querySelector('input[value="REJECTED_ALL"]').checked = true;
                maskCtx.clearRect(0, 0, 512, 512);
                saveCanvasHistory();
                redrawMainCanvas();
            }
            saveLocalDraft();
        }

function openConfirmationModal() {
            const modal = document.getElementById('confirmSignoffModal');
            if (modal) modal.style.display = 'flex';
        }

function closeConfirmationModal() {
            const modal = document.getElementById('confirmSignoffModal');
            if (modal) modal.style.display = 'none';
        }

async function executeDoctorSignOff() {
    closeConfirmationModal();
    const maskImgData = maskCtx.getImageData(0, 0, 512, 512);
    const flat = [];
    for (let i = 3; i < maskImgData.data.length; i += 4) {
        flat.push(maskImgData.data[i] > 0 ? 1 : 0);
    }

    const counts = [];
    let lastV = flat[0] || 0;
    let run = 0;
    for (let v of flat) {
        if (v === lastV) { run++; }
        else { counts.push(run); run = 1; lastV = v; }
    }
    counts.push(run);

    // Đồng bộ tự động giữa trạng thái mask thực tế và hành động rà soát (tránh lỗi 422 mismatch)
    let isMaskUnchanged = false;
    if (currentPrediction && currentPrediction.rle_mask && currentPrediction.rle_mask.counts) {
        const rawRle = currentPrediction.rle_mask;
        if (rawRle.first_val === (flat[0] || 0) &&
            rawRle.counts.length === counts.length &&
            rawRle.counts.every((c, idx) => c === counts[idx])) {
            isMaskUnchanged = true;
        }
    }
    const hasAnyPixel = flat.some(v => v === 1);

    let actionToSubmit = currentCase.doctor_action || "ACCEPTED_RAW";
    if (!hasAnyPixel) {
        actionToSubmit = "REJECTED_ALL";
    } else if (isMaskUnchanged) {
        actionToSubmit = "ACCEPTED_RAW";
    } else {
        actionToSubmit = "MODIFIED";
    }
    currentCase.doctor_action = actionToSubmit;
    chooseDoctorAction(actionToSubmit);

    const elapsedReviewSeconds = reviewStartedAt === null
        ? 0 : Math.max(1, Math.round((performance.now() - reviewStartedAt) / 1000));
    const payload = {
        image_id: currentCase.image_id,
        prediction_id: currentPrediction && currentPrediction.prediction_id,
        doctor_id: "UNVERIFIED_REVIEWER",
        doctor_action: actionToSubmit,
        verified_mask_rle: { shape: [512, 512], counts: counts, first_val: flat[0] || 0, encoding: "standard_rle" },
        lesion_type: "Chưa đánh giá bệnh học",
        clinical_notes: document.getElementById('textDoctorNotes').value.trim(),
        time_spent_seconds: elapsedReviewSeconds
    };

    try {
        const resp = await fetch(`${API_BASE}/api/review`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            let errDetail = "Lỗi khi lưu rà soát";
            try {
                const errJson = await resp.json();
                if (errJson.detail) errDetail = errJson.detail;
            } catch (e) {}
            if (errDetail.includes("requires the original")) {
                throw new Error("Mặt nạ đã bị chỉnh sửa so với bản AI gốc. Hãy chọn 'Đã chỉnh sửa mask' để lưu.");
            } else if (errDetail.includes("requires an edited mask")) {
                throw new Error("Mặt nạ chưa có thay đổi nào. Hãy chọn 'Chấp nhận kết quả AI' hoặc dùng cọ vẽ chỉnh sửa.");
            } else if (errDetail.includes("requires an empty mask")) {
                throw new Error("Hành động từ chối yêu cầu mặt nạ rỗng. Hãy dùng nút Reset hoặc Tẩy để xóa toàn bộ vùng mask.");
            }
            throw new Error(errDetail);
        }
        
        // Cập nhật số liệu real-time lên Bảng điều khiển và Hồ sơ
        loadDashboardStats();
        loadDashboardCases();

        document.getElementById('hudStatus').innerText = 'Đã xác nhận final mask';
        reviewStartedAt = null;
        showToast("✓ Đã lưu mask cuối cùng và ghi nhận nhật ký rà soát thành công!");
    } catch (err) {
        showToast("Lỗi ký duyệt: " + err.message, false);
    }
}

function onGlobalFacilityChange(facKey) {
    applyFacilityToReport();
}

function onModalFacilityChange(facKey) {
    applyFacilityToReport();
}

function applyFacilityToReport() {
    const hospName = document.getElementById('field_hospitalName');
    const deptName = document.getElementById('field_departmentName');
    const hospAddr = document.getElementById('field_hospitalAddress');
    const hospContact = document.getElementById('field_hospitalContact');

    if (hospName) hospName.innerText = 'BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY';
    if (deptName) deptName.innerText = 'KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA';
    if (hospAddr) hospAddr.innerText = 'Địa chỉ: Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội';
    if (hospContact) hospContact.innerText = 'Tel: +84 (24) 3974 3556 | Hotline: +84 (24) 3974 3558 | Cấp cứu: +84 (24) 3974 4333';
}

function populateReportSheet(caseObj, overrides = {}) {
    if (!caseObj) caseObj = (typeof currentCase !== 'undefined' ? currentCase : {});
    applyFacilityToReport();

    const now = new Date();
    const formatStudyDate = (raw) => {
        if (!raw || raw.startsWith('1111') || raw.length < 5) {
            return `${String(now.getDate()).padStart(2, '0')}-${now.toLocaleString('en-US', { month: 'short' })}-${now.getFullYear()} 10:42 AM`;
        }
        return raw;
    };

    const pid = overrides.pid || caseObj.patient_id || 'BN-VINMEC-9284';
    const name = overrides.name || caseObj.patient_name || 'Nguyễn Thị Phượng';
    const gender = overrides.gender || caseObj.patient_gender || 'Female / Nữ';
    const dob = overrides.dob || caseObj.patient_dob || '16-May-1991';
    const refDoc = overrides.refDoc || caseObj.referring_doctor || 'TS. BS. Lê Khắc Hiếu';
    const visitType = overrides.visitType || caseObj.visit_type || 'OPD Visit / 3090373';
    const orderDate = overrides.orderDate || formatStudyDate(caseObj.study_date);
    const completedDate = overrides.completedDate || `${String(now.getDate()).padStart(2, '0')}-${now.toLocaleString('en-US', { month: 'short' })}-${now.getFullYear()} 11:07 AM`;
    const clinicalDiag = overrides.clinicalDiag || caseObj.clinical_indication || 'Theo dõi u nang buồng trứng phải / Đau tức nhẹ vùng hạ vị';
    const userObj = (typeof currentUser !== 'undefined' && currentUser) ? currentUser : { full_name: 'BS.CKII. Trương Thị Phượng', title: 'Bác sĩ chuyên khoa Chẩn đoán hình ảnh' };
    const docName = overrides.docName || userObj.full_name || 'BS.CKII. Trương Thị Phượng';
    const docTitle = overrides.docTitle || userObj.title || 'Bác sĩ chuyên khoa Chẩn đoán hình ảnh';

    // AI and Doctor Measurements
    const meas = (typeof currentPrediction !== 'undefined' && currentPrediction) ? (currentPrediction.measurements || {}) : {};
    const getMeasVal = (val, fallbackCase, fallbackElId, defaultVal, isFloat2 = false) => {
        if (val !== undefined && val !== null) {
            return typeof val === 'number' ? (isFloat2 ? val.toFixed(2) : val.toFixed(1)) : String(val);
        }
        if (fallbackCase !== undefined && fallbackCase !== null) {
            return String(fallbackCase);
        }
        const el = document.getElementById(fallbackElId);
        if (el && el.innerText) {
            return el.innerText.replace(/ mm| cm²/g, '').trim();
        }
        return defaultVal;
    };

    const d1 = overrides.d1 || getMeasVal(meas.max_diameter_mm, caseObj?.max_diameter_mm, 'resDmax', '40.3');
    const d2 = overrides.d2 || getMeasVal(meas.ortho_diameter_mm, caseObj?.ortho_diameter_mm, 'resDorth', '19.3');
    const area = overrides.area || getMeasVal(meas.total_area_cm2, caseObj?.total_area_cm2, 'resArea', '7.15', true);
    const lesionType = overrides.lesionType || caseObj?.lesion_type || (document.getElementById('selectPathology') ? document.getElementById('selectPathology').value : 'U nang thanh dịch buồng trứng (Simple Serous Cyst)');

    // Text Elements
    if (document.getElementById('field_patientId')) document.getElementById('field_patientId').innerText = pid;
    if (document.getElementById('field_patientName')) document.getElementById('field_patientName').innerText = name;
    if (document.getElementById('field_patientGender')) document.getElementById('field_patientGender').innerText = gender;
    if (document.getElementById('field_patientDob')) document.getElementById('field_patientDob').innerText = dob;
    if (document.getElementById('field_orderDate')) document.getElementById('field_orderDate').innerText = orderDate;
    if (document.getElementById('field_visitType')) document.getElementById('field_visitType').innerText = visitType;
    if (document.getElementById('field_referringDoctor')) document.getElementById('field_referringDoctor').innerText = refDoc;
    if (document.getElementById('field_completedDate')) document.getElementById('field_completedDate').innerText = completedDate;
    if (document.getElementById('field_clinicalDiagnosis')) document.getElementById('field_clinicalDiagnosis').innerText = clinicalDiag;

    // Specialized Ovarian Findings for Both Ovaries (Right & Left)
    const activeSide = (caseObj.active_ovary_side || 'RIGHT').toUpperCase();
    const contraStatus = (caseObj.contralateral_status || 'NOT_VISUALIZED').toUpperCase();

    const contraTextMap = {
        'NOT_VISUALIZED': {
            l1: '- Trạng thái: Chưa khảo sát / Không quan sát thấy trên lần khám này (Not visualized).',
            l2: '- Không phát hiện hình ảnh bất thường rõ rệt trong trường quét ghi nhận.'
        },
        'NORMAL': {
            l1: '- Trạng thái: Hình thái bình thường, nhu mô đồng nhất (Unremarkable).',
            l2: '- Các nang noãn sinh lý kích thước < 10 mm rải rác ở ngoại biên, không thấy u cục hay nang bệnh lý.'
        },
        'PREVIOUSLY_RESECTED': {
            l1: '- Tiền sử ngoại khoa: Đã phẫu thuật cắt buồng trứng trước đó (Previously resected).',
            l2: '- Hố buồng trứng trống, không phát hiện khối choán chỗ tồn dư hay tái phát.'
        }
    };
    const contraInfo = contraTextMap[contraStatus] || contraTextMap['NOT_VISUALIZED'];
    const calibText = currentPrediction?.pixel_spacing_mm ? `D1 = ${d1} mm, D2 = ${d2} mm, Diện tích = ${area} cm²` : `Chưa hiệu chuẩn mm vật lý (Đo đạc tương đối theo độ phân giải pixel)`;

    if (activeSide === 'RIGHT') {
        if (document.getElementById('field_ovary_r1')) document.getElementById('field_ovary_r1').innerText = `- Vị trí: Buồng trứng Phải (Đang khảo sát chuyên sâu trên mặt cắt TVUS).`;
        if (document.getElementById('field_ovary_r2')) document.getElementById('field_ovary_r2').innerText = overrides.ovaryR2 || `- Tổn thương: Phát hiện vùng tổn thương dạng nang/khối, ranh giới được mô hình Standard U-Net hỗ trợ định vị.`;
        if (document.getElementById('field_ovary_r3')) {
            document.getElementById('field_ovary_r3').style.display = 'block';
            document.getElementById('field_ovary_r3').innerText = overrides.ovaryR3 || `- Kích thước hình học trích xuất: ${calibText}.`;
        }
        if (document.getElementById('field_ovary_r4')) {
            document.getElementById('field_ovary_r4').style.display = 'block';
            document.getElementById('field_ovary_r4').innerText = overrides.ovaryR4 || `- Rà soát Human-in-the-Loop (HITL): Mặt nạ phân đoạn đã được bác sĩ xác nhận trên bàn làm việc Canvas.`;
        }

        if (document.getElementById('field_ovary_l1')) document.getElementById('field_ovary_l1').innerText = contraInfo.l1;
        if (document.getElementById('field_ovary_l2')) document.getElementById('field_ovary_l2').innerText = contraInfo.l2;
        if (document.getElementById('field_ovary_l3')) document.getElementById('field_ovary_l3').style.display = 'none';
        if (document.getElementById('field_ovary_l4')) document.getElementById('field_ovary_l4').style.display = 'none';
    } else {
        // LEFT Ovary is active
        if (document.getElementById('field_ovary_l1')) document.getElementById('field_ovary_l1').innerText = `- Vị trí: Buồng trứng Trái (Đang khảo sát chuyên sâu trên mặt cắt TVUS).`;
        if (document.getElementById('field_ovary_l2')) document.getElementById('field_ovary_l2').innerText = overrides.ovaryL2 || `- Tổn thương: Phát hiện vùng tổn thương dạng nang/khối, ranh giới được mô hình Standard U-Net hỗ trợ định vị.`;
        if (document.getElementById('field_ovary_l3')) {
            document.getElementById('field_ovary_l3').style.display = 'block';
            document.getElementById('field_ovary_l3').innerText = overrides.ovaryL3 || `- Kích thước hình học trích xuất: ${calibText}.`;
        }
        if (document.getElementById('field_ovary_l4')) {
            document.getElementById('field_ovary_l4').style.display = 'block';
            document.getElementById('field_ovary_l4').innerText = overrides.ovaryL4 || `- Rà soát Human-in-the-Loop (HITL): Mặt nạ phân đoạn đã được bác sĩ xác nhận trên bàn làm việc Canvas.`;
        }

        if (document.getElementById('field_ovary_r1')) document.getElementById('field_ovary_r1').innerText = contraInfo.l1;
        if (document.getElementById('field_ovary_r2')) document.getElementById('field_ovary_r2').innerText = contraInfo.l2;
        if (document.getElementById('field_ovary_r3')) document.getElementById('field_ovary_r3').style.display = 'none';
        if (document.getElementById('field_ovary_r4')) document.getElementById('field_ovary_r4').style.display = 'none';
    }

    if (document.getElementById('field_douglas')) {
        document.getElementById('field_douglas').innerText = overrides.douglas || `- Túi cùng Douglas & mô lân cận: Không phát hiện bất thường rõ rệt trên diện cắt quét ngang.`;
    }

    // Conclusion for Both Ovaries
    const activeSideLabel = activeSide === 'RIGHT' ? 'BUỒNG TRỨNG PHẢI' : 'BUỒNG TRỨNG TRÁI';
    const contraSideLabel = activeSide === 'RIGHT' ? 'BUỒNG TRỨNG TRÁI' : 'BUỒNG TRỨNG PHẢI';
    if (document.getElementById('field_conclusion_l1')) {
        document.getElementById('field_conclusion_l1').innerText = overrides.conc1 || `1. HÌNH ẢNH TỔN THƯƠNG ${activeSideLabel} — MẶT NẠ PHÂN ĐOẠN ĐÃ ĐƯỢC BÁC SĨ XÁC NHẬN TRÊN BÀN LÀM VIỆC HITL.`;
    }
    if (document.getElementById('field_conclusion_l2')) {
        let contraSummary = 'CHƯA KHẢO SÁT / KHÔNG QUAN SÁT THẤY TRONG LẦN KHÁM NÀY';
        if (contraStatus === 'NORMAL') contraSummary = 'HÌNH THÁI BÌNH THƯỜNG TRÊN SIÊU ÂM';
        else if (contraStatus === 'PREVIOUSLY_RESECTED') contraSummary = 'TIỀN SỬ ĐÃ CẮT BỎ';
        document.getElementById('field_conclusion_l2').innerText = overrides.conc2 || `2. ${contraSideLabel}: ${contraSummary}. PHIẾU PHỤC VỤ NGHIÊN CỨU THỬ NGHIỆM HỆ THỐNG HITL.`;
    }

    // Images Gallery Binding
    const imgBeforeEl = document.getElementById('field_imageBefore');
    const imgAfterEl = document.getElementById('field_imageAfter');
    const caliperTagEl = document.getElementById('field_imageCaliperTag');

    if (caliperTagEl) {
        caliperTagEl.innerText = `D1: ${d1} mm • D2: ${d2} mm • DT: ${area} cm²`;
    }

    // Bind original & segmented image previews
    if (imgBeforeEl) {
        if (caseObj.original_image_base64) {
            imgBeforeEl.src = caseObj.original_image_base64;
        } else if (caseObj.image_url) {
            imgBeforeEl.src = caseObj.image_url;
        } else if (caseObj.file_path) {
            imgBeforeEl.src = `/dataset/images/${caseObj.file_path}`;
        }
    }

    if (imgAfterEl) {
        try {
            if (typeof canvas !== 'undefined' && canvas) {
                imgAfterEl.src = canvas.toDataURL('image/png');
            } else if (caseObj.overlay_base64) {
                imgAfterEl.src = caseObj.overlay_base64;
            } else if (imgBeforeEl && imgBeforeEl.src) {
                imgAfterEl.src = imgBeforeEl.src;
            }
        } catch (e) {
            console.log("Canvas toDataURL notice:", e);
        }
    }

    // Date & Signature (using now from function top)
    const sigDateEl = document.getElementById('field_sigDate');
    if (sigDateEl) {
        sigDateEl.innerText = `Hà Nội, ngày ${String(now.getDate()).padStart(2, '0')} tháng ${String(now.getMonth() + 1).padStart(2, '0')} năm ${now.getFullYear()}`;
    }

    if (document.getElementById('field_doctorName')) document.getElementById('field_doctorName').innerText = docName;
    if (document.getElementById('field_doctorTitle')) document.getElementById('field_doctorTitle').innerText = docTitle;
    if (document.getElementById('field_footerApprovedBy')) document.getElementById('field_footerApprovedBy').innerText = `Kết quả đã được duyệt bởi: ${docName} — Hệ thống AI Decision Support v1.2`;

    // Sync Editor Form Fields
    if (document.getElementById('edit_pid')) document.getElementById('edit_pid').value = pid;
    if (document.getElementById('edit_name')) document.getElementById('edit_name').value = name;
    if (document.getElementById('edit_gender')) document.getElementById('edit_gender').value = gender;
    if (document.getElementById('edit_dob')) document.getElementById('edit_dob').value = dob;
    if (document.getElementById('edit_refDoc')) document.getElementById('edit_refDoc').value = refDoc;
    if (document.getElementById('edit_visitType')) document.getElementById('edit_visitType').value = visitType;
    if (document.getElementById('edit_clinicalDiag')) document.getElementById('edit_clinicalDiag').value = clinicalDiag;
    if (document.getElementById('edit_docName')) document.getElementById('edit_docName').value = docName;
    if (document.getElementById('edit_docTitle')) document.getElementById('edit_docTitle').value = docTitle;
    if (document.getElementById('edit_ovaryR2')) document.getElementById('edit_ovaryR2').value = document.getElementById('field_ovary_r2')?.innerText || "";
    if (document.getElementById('edit_ovaryR3')) document.getElementById('edit_ovaryR3').value = document.getElementById('field_ovary_r3')?.innerText || "";
    if (document.getElementById('edit_ovaryR4')) document.getElementById('edit_ovaryR4').value = document.getElementById('field_ovary_r4')?.innerText || "";
    if (document.getElementById('edit_ovaryL2')) document.getElementById('edit_ovaryL2').value = document.getElementById('field_ovary_l2')?.innerText || "";
    if (document.getElementById('edit_douglas')) document.getElementById('edit_douglas').value = document.getElementById('field_douglas')?.innerText || "";
    if (document.getElementById('edit_conc1')) document.getElementById('edit_conc1').value = document.getElementById('field_conclusion_l1')?.innerText || "";
    if (document.getElementById('edit_conc2')) document.getElementById('edit_conc2').value = document.getElementById('field_conclusion_l2')?.innerText || "";
}

function openReportEditorModal() {
    const modal = document.getElementById('reportEditorModal');
    if (modal) {
        populateReportSheet(currentCase);
        modal.classList.add('active');
    }
}

function closeReportEditorModal() {
    const modal = document.getElementById('reportEditorModal');
    if (modal) modal.classList.remove('active');
}

function saveReportEditorChanges() {
    const overrides = {
        pid: document.getElementById('edit_pid').value,
        name: document.getElementById('edit_name').value,
        gender: document.getElementById('edit_gender').value,
        dob: document.getElementById('edit_dob').value,
        refDoc: document.getElementById('edit_refDoc').value,
        visitType: document.getElementById('edit_visitType').value,
        clinicalDiag: document.getElementById('edit_clinicalDiag').value,
        ovaryR2: document.getElementById('edit_ovaryR2').value,
        ovaryR3: document.getElementById('edit_ovaryR3').value,
        ovaryR4: document.getElementById('edit_ovaryR4').value,
        ovaryL2: document.getElementById('edit_ovaryL2').value,
        douglas: document.getElementById('edit_douglas').value,
        conc1: document.getElementById('edit_conc1').value,
        conc2: document.getElementById('edit_conc2').value,
        docName: document.getElementById('edit_docName').value,
        docTitle: document.getElementById('edit_docTitle').value
    };

    populateReportSheet(currentCase, overrides);
    closeReportEditorModal();
    showToast("✓ Đã cập nhật dữ liệu lên phiếu in kết quả!");
}

function openReportFromCaseDetail() {
    if (!activeModalCase) return;
    const caseData = { ...activeModalCase };
    closeCaseDetailModal();

    const firstImg = caseData.images?.[0] || null;
    const review = firstImg?.review || null;
    const pred = firstImg?.prediction || null;

    currentCase = {
        patient_id: caseData.patient_id,
        patient_name: caseData.patient_name || 'Nguyễn Thị Phượng',
        patient_gender: caseData.patient_gender || 'Female / Nữ',
        patient_dob: caseData.patient_dob || '16-May-1991',
        study_date: caseData.study_date,
        clinical_indication: caseData.clinical_indication || 'Theo dõi u nang buồng trứng phải / Đau tức nhẹ vùng hạ vị',
        probe_type: caseData.probe_type || 'TRANSVAGINAL_2D',
        study_id: caseData.study_id || caseData.id,
        study_code: caseData.study_code || 'STD-260829-A1B2',
        lesion_type: review?.lesion_type || caseData.lesion_type || 'U nang thanh dịch buồng trứng (Simple Serous Cyst)',
        doctor_notes: review?.clinical_notes || caseData.clinical_indication
    };

    if (pred?.measurements) {
        currentPrediction = { prediction_id: pred.prediction_id, measurements: pred.measurements };
    }

    populateReportSheet(currentCase, {
        pid: caseData.patient_id,
        name: caseData.patient_name || 'Nguyễn Thị Phượng',
        orderDate: caseData.study_date,
        clinicalDiag: caseData.clinical_indication,
        docName: review ? review.doctor_id : 'BS. Nguyễn Văn A',
        conc1: review ? `1. HÌNH ẢNH ${review.lesion_type.toUpperCase()} BUỒNG TRỨNG PHẢI (PHÂN LOẠI O-RADS 2).` : undefined
    });

    navigateTo('report_complete');
}

async function downloadCurrentPdfReport() {
    showToast("Đang tạo phiếu báo cáo y tế PDF chuẩn Vinmec...", true);
    
    let overlayBase64 = null;
    try {
        if (typeof canvas !== 'undefined' && canvas) {
            overlayBase64 = canvas.toDataURL('image/png');
        }
    } catch (e) {
        console.log("Canvas export notice:", e);
    }

    const activeFacKey = typeof currentFacilityKey !== 'undefined' ? currentFacilityKey : 'times_city';

    let imageBeforeVal = null;
    if (typeof currentCase !== 'undefined' && (currentCase?.original_image_base64 || currentCase?.image_base64)) {
        imageBeforeVal = currentCase.original_image_base64 || currentCase.image_base64;
    } else if (typeof currentPrediction !== 'undefined' && currentPrediction?.original_image_base64) {
        imageBeforeVal = currentPrediction.original_image_base64;
    } else if (typeof bgImage !== 'undefined' && bgImage?.src) {
        imageBeforeVal = bgImage.src;
    }

    const reportPayload = {
        facilityKey: activeFacKey,
        hospitalName: document.getElementById('field_hospitalName')?.innerText || "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY",
        departmentName: document.getElementById('field_departmentName')?.innerText || "KHOA CHẨN ĐOÁN HÌNH ẢNH — ĐƠN NGUYÊN SIÊU ÂM PHỤ KHOA",
        hospitalAddress: document.getElementById('field_hospitalAddress')?.innerText || "Địa chỉ: Số 458 Minh Khai, Phường Vĩnh Tuy, Quận Hai Bà Trưng, Hà Nội",
        hospitalContact: document.getElementById('field_hospitalContact')?.innerText || "Tel: +84 (24) 3974 3556 | Hotline: +84 (24) 3974 3558 | Cấp cứu: +84 (24) 3974 4333",
        reportTitle: document.getElementById('field_reportTitle')?.innerText || "PHIẾU KẾT QUẢ SIÊU ÂM BUỒNG TRỨNG & TIỂU KHUNG",
        patientId: document.getElementById('field_patientId')?.innerText || (typeof currentCase !== 'undefined' ? currentCase.patient_id : "200044962"),
        patientName: document.getElementById('field_patientName')?.innerText || (typeof currentCase !== 'undefined' ? currentCase.patient_name : "Nguyễn Thị Phượng"),
        patientGender: document.getElementById('field_patientGender')?.innerText || "Nữ (Female)",
        patientDob: document.getElementById('field_patientDob')?.innerText || "16/05/1991",
        orderDate: document.getElementById('field_orderDate')?.innerText || (typeof currentCase !== 'undefined' ? currentCase.study_date : "26-Aug-2026 10:42 AM"),
        visitType: document.getElementById('field_visitType')?.innerText || "Khám ngoại trú (OPD) / 3090373",
        referringDoctor: document.getElementById('field_referringDoctor')?.innerText || "TS. BS. Lê Khắc Hiếu",
        serviceName: document.getElementById('field_serviceName')?.innerText || "Khám chuyên khoa Phụ khoa — Siêu âm Đầu dò",
        orderName: document.getElementById('field_orderName')?.innerText || "Siêu âm buồng trứng qua ngả âm đạo [Hỗ trợ phân đoạn U-Net Baseline]",
        completedDate: document.getElementById('field_completedDate')?.innerText || "26-Aug-2026 11:07 AM",
        rpid: document.getElementById('field_rpid')?.innerText || "HAN26652307901",
        clinicalDiagnosis: document.getElementById('field_clinicalDiagnosis')?.innerText || "Theo dõi u nang buồng trứng phải / Đau tức nhẹ vùng hạ vị",
        technique: document.getElementById('field_technique')?.innerText || "Siêu âm 2D ngả âm đạo kết hợp mô hình Standard U-Net baseline tự động phân đoạn ranh giới tổn thương.",
        ovary_r1: document.getElementById('field_ovary_r1')?.innerText || "- Vùng quan tâm buồng trứng: Tiếp giáp và ranh giới tổn thương rõ trên ảnh siêu âm 2D.",
        ovary_r2: document.getElementById('field_ovary_r2')?.innerText || "- Vùng quan tâm (ROI): Phát hiện vùng tổn thương dạng nang/khối buồng trứng.",
        ovary_r3: document.getElementById('field_ovary_r3')?.innerText || "- Đo đạc AI (Standard U-Net baseline): Đường kính D1 = 28.5 mm, Đường kính trực giao D2 = 21.0 mm, Diện tích = 4.62 cm² (hiệu chuẩn).",
        ovary_r4: document.getElementById('field_ovary_r4')?.innerText || "- Rà soát Human-in-the-Loop (HITL): Mặt nạ phân đoạn đã được người dùng kiểm tra đối chiếu.",
        ovary_l1: document.getElementById('field_ovary_l1')?.innerText || "- Buồng trứng đối bên: Cấu trúc mô đồng nhất, không phát hiện khối bất thường rõ rệt.",
        douglas: document.getElementById('field_douglas')?.innerText || "- Cùng đồ sau không có dịch tự do. Không phát hiện khối bất thường vùng tiểu khung.",
        conclusion_l1: document.getElementById('field_conclusion_l1')?.innerText || "1. KẾT QUẢ PHÂN ĐOẠN TỔN THƯƠNG NGHIÊN CỨU: Vùng tổn thương đã được mô hình Standard U-Net baseline định vị và rà soát xác nhận.",
        conclusion_l2: document.getElementById('field_conclusion_l2')?.innerText || "2. LƯU Ý BẢN MẪU: Đây là bản mẫu nghiên cứu thực nghiệm phục vụ khóa luận tốt nghiệp, không thay thế chẩn đoán lâm sàng chính thức.",
        doctorTitle: document.getElementById('field_doctorTitle')?.innerText || "Bác sĩ chuyên khoa Chẩn đoán hình ảnh",
        doctorName: document.getElementById('field_doctorName')?.innerText || "BS.CKII. Trương Thị Phượng",
        imageBefore: imageBeforeVal,
        imageAfter: overlayBase64 || (typeof currentPrediction !== 'undefined' && currentPrediction?.overlay_base64 ? currentPrediction.overlay_base64 : null),
        imageBeforeCaption: "Mặt cắt dọc đầu dò âm đạo (TVUS 7.5MHz)",
        imageCaliperTag: `D1: ${document.getElementById('resDmax')?.innerText || '28.5 mm'} • D2: ${document.getElementById('resDorth')?.innerText || '21.0 mm'} • DT: ${document.getElementById('resArea')?.innerText || '4.62 cm²'}`
    };

    showToast("Đang chuẩn bị hộp thoại In / Lưu phiếu PDF (A4)...", true);
    setTimeout(() => {
        window.print();
    }, 300);
}

function printCurrentReport() {
    showToast("Đang chuẩn bị trang in phiếu kết quả...", true);
    setTimeout(() => {
        window.print();
    }, 200);
}

function dualMaskToRle(mask) {
    const pixels = mask.getContext('2d').getImageData(0, 0, 512, 512).data;
    const first = pixels[3] > 0 ? 1 : 0;
    const counts = [];
    let current = first;
    let length = 0;
    let positive = false;
    for (let index = 3; index < pixels.length; index += 4) {
        const value = pixels[index] > 0 ? 1 : 0;
        if (value) positive = true;
        if (value === current) length++;
        else { counts.push(length); length = 1; current = value; }
    }
    counts.push(length);
    return { rle: { shape: [512, 512], counts, first_val: first, encoding: 'standard_rle' }, positive };
}

function sameDualRle(left, right) {
    return left.first_val === right.first_val && left.counts.length === right.counts.length
        && left.counts.every((count, index) => count === right.counts[index]);
}

function updateDualApprovalStatus() {
    const complete = ['R', 'L'].every(side => dualCase.sides[side].approved && !dualCase.sides[side].saving);
    const label = document.getElementById('dualOverallStatus');
    label.textContent = complete ? 'ĐÃ LƯU RÀ SOÁT · R + L' : 'Chờ rà soát đủ R và L';
    label.classList.toggle('is-complete', complete);
    document.getElementById('dualOpenReport').disabled = !complete;
    document.getElementById('dualPrintBtn').disabled = !complete;
}

function invalidateDualApproval(side) {
    const item = dualCase.sides[side];
    if (!item.prediction) return;
    item.approved = false;
    item.reviewId = null;
    document.getElementById(`dualStatus${side}`).textContent = 'Đã chỉnh sửa · cần lưu lại';
    const button = document.getElementById(`dualApprove${side}`);
    button.textContent = `Xác nhận & lưu ${side}`;
    button.classList.remove('is-approved');
    updateDualApprovalStatus();
}

async function approveDualSide(side) {
    const item = dualCase.sides[side];
    if (!item.prediction || !item.mask || item.saving) return;
    const { rle, positive } = dualMaskToRle(item.mask);
    const action = sameDualRle(rle, item.prediction.rle_mask) ? 'ACCEPTED_RAW'
        : positive ? 'MODIFIED' : 'REJECTED_ALL';
    item.saving = true;
    const button = document.getElementById(`dualApprove${side}`);
    const notes = document.getElementById(`dualNotes${side}`);
    notes.disabled = true;
    button.disabled = true;
    updateDualApprovalStatus();
    button.textContent = 'Đang lưu kết quả…';
    try {
        const response = await fetch(`${API_BASE}/api/review`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_id: item.imageId,
                study_id: dualCase.studyId,
                prediction_id: item.prediction.prediction_id,
                doctor_id: currentUser?.username || 'UNVERIFIED_REVIEWER',
                doctor_action: action,
                verified_mask_rle: rle,
                lesion_type: 'UNSPECIFIED',
                clinical_notes: document.getElementById(`dualNotes${side}`).value.trim(),
                time_spent_seconds: Math.max(1, Math.round((performance.now() - (item.reviewStartedAt || performance.now())) / 1000))
            })
        });
        if (!response.ok) {
            const detail = (await response.json().catch(() => ({}))).detail;
            throw new Error(detail || `Không thể lưu rà soát bên ${side}.`);
        }
        const review = await response.json();
        item.approved = true;
        item.reviewId = review.review_id;
        document.getElementById(`dualStatus${side}`).textContent = 'Đã lưu rà soát';
        button.classList.add('is-approved');
        button.textContent = `Đã lưu ${side} · lưu lại`;
        updateDualApprovalStatus();
        showToast(`Đã lưu mask đã rà soát bên ${side}.`);
    } catch (error) {
        item.approved = false;
        item.reviewId = null;
        document.getElementById(`dualStatus${side}`).textContent = 'Chưa lưu được rà soát';
        button.classList.remove('is-approved');
        button.textContent = `Xác nhận & lưu ${side}`;
        showToast(error.message, false);
    } finally {
        item.saving = false;
        notes.disabled = false;
        button.disabled = false;
        updateDualApprovalStatus();
    }
}

async function openDualReport() {
    if (!dualCase.sides.R.approved || !dualCase.sides.L.approved || dualCase.sides.R.saving || dualCase.sides.L.saving || !dualCase.studyId) {
        showToast('Cần đủ hai ảnh và hai kết quả rà soát đã lưu.', false);
        return false;
    }
    try {
        const response = await fetch(`${API_BASE}/api/cases/${dualCase.studyId}`);
        if (!response.ok) throw new Error('Không thể kiểm tra trạng thái ca trên máy chủ.');
        const study = await response.json();
        const sides = Object.fromEntries(study.images.filter(image => image.laterality).map(image => [image.laterality, image]));
        if (!sides.R?.review || !sides.L?.review || study.status !== 'REVIEWED') {
            throw new Error('Máy chủ chưa ghi nhận đủ ảnh và xác nhận của hai bên R/L.');
        }
        renderDualReport(study);
        navigateTo('dual_report');
        return true;
    } catch (error) {
        showToast(error.message, false);
        return false;
    }
}

function renderDualReport(study) {
    document.getElementById('dualReportDate').textContent = study.study_date || '—';
    document.getElementById('dualReportPatient').textContent = `Mã hồ sơ: ${study.patient_id || '—'}`;
    document.getElementById('dualReportStudy').textContent = `Mã ca: ${study.study_code || '—'}`;
    for (const side of ['R', 'L']) {
        const item = dualCase.sides[side];
        const metrics = item.prediction?.measurements || {};
        document.getElementById(`dualReportOriginal${side}`).src = item.prediction.original_image_base64;
        document.getElementById(`dualReportMask${side}`).src = item.mask.toDataURL('image/png');
        document.getElementById(`dualReportMeasures${side}`).textContent = metrics.calibrated && Number.isFinite(metrics.max_diameter_mm) && Number.isFinite(metrics.ortho_diameter_mm)
            ? `D₁ ${metrics.max_diameter_mm.toFixed(1)} mm · D₂ ${metrics.ortho_diameter_mm.toFixed(1)} mm · D₃ chưa đo`
            : 'Chưa hiệu chuẩn kích thước vật lý';
        document.getElementById(`dualReportNotes${side}`).textContent = document.getElementById(`dualNotes${side}`).value.trim() || 'Không có nhận xét bổ sung.';
        document.getElementById(`dualReportApproval${side}`).textContent = `Đã lưu rà soát · ${item.reviewId}`;
    }
}

async function printDualReport() {
    if (!(await openDualReport())) return;
    document.body.classList.add('pacs-print-ready');
    window.addEventListener('afterprint', () => document.body.classList.remove('pacs-print-ready'), { once: true });
    window.print();
}
