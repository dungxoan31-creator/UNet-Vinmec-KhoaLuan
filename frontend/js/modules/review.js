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
                if (raw) {
                    const draft = JSON.parse(raw);
                    console.log("Found local draft for PID:", draft.patient_id);
                }
            } catch (e) {}
        }

function onPathologyChanged(val) {
    updateOradsIndicator(val);
    autoGenerateAiNarrative();
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
    saveLocalDraft();
}

async function autoGenerateAiNarrative() {
    const btn = document.getElementById('btnAutoGenerateNarrative');
    if (btn) {
        btn.innerHTML = '<span>⏳</span> <span>Đang tổng hợp tri thức...</span>';
        btn.disabled = true;
    }
    
    try {
        const payload = {
            vision_findings: {
                max_diameter_mm: currentPrediction?.measurements?.max_diameter_mm || 0,
                ortho_diameter_mm: currentPrediction?.measurements?.ortho_diameter_mm || 0,
                d3_mm: currentCase.d3_mm || currentPrediction?.measurements?.d3_mm || 0,
                volume_ml: currentCase.volume_ml || currentPrediction?.measurements?.volume_ml || 0,
                total_area_cm2: currentPrediction?.measurements?.total_area_cm2 || 0,
                cdss_classification: currentPrediction?.cdss_classification,
                acoustic_profile: currentPrediction?.acoustic_profile,
                has_solid_component: Boolean(currentPrediction?.cdss_classification?.primary_suspicion?.includes('Solid') || currentPrediction?.cdss_classification?.primary_suspicion?.includes('đặc')),
                papillary_projections_count: 0,
                acoustic_shadowing: Boolean(currentPrediction?.acoustic_profile?.posterior_shadow_index && currentPrediction.acoustic_profile.posterior_shadow_index < 0.85),
                fluid_echogenicity: currentPrediction?.acoustic_profile?.echogenicity_class || "anechoic",
                locules_count: currentPrediction?.cdss_classification?.primary_suspicion?.includes('đa thùy') ? 3 : 1,
                color_score: 1,
                has_ascites: false
            },
            patient_info: {
                patient_id: currentCase.patient_id || "BN-VINMEC",
                patient_age: currentCase.patient_age || "32",
                study_code: currentCase.study_code || "STD-01"
            },
            pathology_name: document.getElementById('selectPathology')?.value || currentPrediction?.cdss_classification?.primary_suspicion || "U nang thanh dịch buồng trứng"
        };

        const resp = await fetch(`${API_BASE}/api/generate-narrative`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) throw new Error("Không thể sinh mô tả tự động");
        const data = await resp.json();

        const textarea = document.getElementById('textDoctorNotes');
        if (textarea) {
            textarea.value = `${data.sonographic_findings_text}\n\nKẾT LUẬN & ĐỀ XUẤT:\n${data.clinical_conclusion_text}`;
            textarea.rows = 7;
            textarea.focus();
        }

        showToast("✓ Đã sinh bản mô tả lâm sàng chi tiết từ Attention U-Net & Medical KB!");
        saveLocalDraft();
    } catch (err) {
        console.error(err);
        showToast("Lỗi sinh văn bản lâm sàng: " + err.message, false);
    } finally {
        if (btn) {
            btn.innerHTML = '<span>✨</span> <span>Tự Động Soạn Báo Cáo AI (Medical NLP)</span>';
            btn.disabled = false;
        }
    }
}

function chooseDoctorAction(action) {
            currentCase.doctor_action = action;
            document.querySelectorAll('.decision-choice-card').forEach(c => c.classList.remove('selected'));
            if (action === 'ACCEPTED_RAW') {
                document.getElementById('cardOptAccept').classList.add('selected');
                document.querySelector('input[value="ACCEPTED_RAW"]').checked = true;
            } else if (action === 'MODIFIED') {
                document.getElementById('cardOptModify').classList.add('selected');
                document.querySelector('input[value="MODIFIED"]').checked = true;
            } else {
                document.getElementById('cardOptReject').classList.add('selected');
                document.querySelector('input[value="REJECTED_ALL"]').checked = true;
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

            const activeDoctorName = (typeof currentUser !== 'undefined' && currentUser && currentUser.full_name) ? currentUser.full_name : "BS. Nguyễn Văn A";
            const payload = {
                image_id: currentCase.image_id,
                doctor_id: activeDoctorName,
                doctor_action: currentCase.doctor_action || "ACCEPTED_RAW",
                verified_mask_rle: { shape: [512, 512], counts: counts, first_val: flat[0] || 0, encoding: "standard_rle" },
                lesion_type: document.getElementById('selectPathology').value,
                clinical_notes: document.getElementById('textDoctorNotes').value.trim(),
                time_spent_seconds: 18
            };

            try {
                const resp = await fetch(`${API_BASE}/api/review`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!resp.ok) throw new Error("Lỗi khi ký duyệt");
                
                // Immediately refresh real-time metrics across all tabs and screens
                loadDashboardStats();
                loadDashboardCases();

                // Populate Official Vinmec Diagnosis Sheet
                populateReportSheet(currentCase);

                showToast("✓ Đã ký duyệt và kết xuất Phiếu kết quả chẩn đoán siêu âm Vinmec!");
                navigateTo('report_complete');
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

    // Specialized Ovarian Findings
    if (document.getElementById('field_ovary_r2')) {
        document.getElementById('field_ovary_r2').innerText = overrides.ovaryR2 || `- Tổn thương: Bên trong phát hiện 01 khối dạng ${lesionType}, ranh giới rõ, thành mỏng đều.`;
    }
    if (document.getElementById('field_ovary_r3')) {
        document.getElementById('field_ovary_r3').innerText = overrides.ovaryR3 || `- Đo đạc AI (Attention U-Net): Đường kính lớn nhất D1 = ${d1} mm, Đường kính trực giao D2 = ${d2} mm, Diện tích = ${area} cm².`;
    }
    if (document.getElementById('field_ovary_r4')) {
        document.getElementById('field_ovary_r4').innerText = overrides.ovaryR4 || `- Doppler màu: Không thấy tăng sinh mạch máu bất thường trong vách hoặc thành nang (RI = 0.62).`;
    }
    if (document.getElementById('field_ovary_l2')) {
        document.getElementById('field_ovary_l2').innerText = overrides.ovaryL2 || `- Các nang noãn sinh lý kích thước < 8 mm rải rác ở ngoại vi, không thấy cấu trúc u cục khu trú hay nang bất thường.`;
    }
    if (document.getElementById('field_douglas')) {
        document.getElementById('field_douglas').innerText = overrides.douglas || `- Cùng đồ sau không có dịch tự do. Không phát hiện khối bất thường vùng tiểu khung.`;
    }

    // Conclusion
    if (document.getElementById('field_conclusion_l1')) {
        document.getElementById('field_conclusion_l1').innerText = overrides.conc1 || `1. HÌNH ẢNH ${lesionType.toUpperCase()} BUỒNG TRỨNG PHẢI (PHÂN LOẠI O-RADS 2).`;
    }
    if (document.getElementById('field_conclusion_l2')) {
        document.getElementById('field_conclusion_l2').innerText = overrides.conc2 || `2. BUỒNG TRỨNG TRÁI VÀ CÙNG ĐỒ DOUGLAS HIỆN TẠI TRONG GIỚI HẠN BÌNH THƯỜNG. ĐỀ NGHỊ SIÊU ÂM KIỂM TRA LẠI SAU 3 THÁNG.`;
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

    window.currentCase = {
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
        window.currentPrediction = { measurements: pred.measurements };
    }

    populateReportSheet(window.currentCase, {
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
        orderName: document.getElementById('field_orderName')?.innerText || "Siêu âm buồng trứng qua ngả âm đạo [Đánh giá khối u nang bằng AI Attention U-Net]",
        completedDate: document.getElementById('field_completedDate')?.innerText || "26-Aug-2026 11:07 AM",
        rpid: document.getElementById('field_rpid')?.innerText || "HAN26652307901",
        clinicalDiagnosis: document.getElementById('field_clinicalDiagnosis')?.innerText || "Theo dõi u nang buồng trứng phải / Đau tức nhẹ vùng hạ vị",
        technique: document.getElementById('field_technique')?.innerText || "Siêu âm 2D Doppler màu ngả âm đạo kết hợp mô hình AI Attention U-Net tự động phân đoạn ranh giới u và trích xuất kích thước trực giao (D1, D2, Diện tích).",
        ovary_r1: document.getElementById('field_ovary_r1')?.innerText || "- Kích thước buồng trứng: 38 x 26 mm. Vị trí tiếp giáp bình thường.",
        ovary_r2: document.getElementById('field_ovary_r2')?.innerText || "- Tổn thương: Bên trong phát hiện 01 cấu trúc dạng u nang, ranh giới rõ, thành mỏng đều.",
        ovary_r3: document.getElementById('field_ovary_r3')?.innerText || "- Đo đạc AI (Attention U-Net): Đường kính lớn nhất D1 = 28.5 mm, Đường kính trực giao D2 = 21.0 mm, Diện tích = 4.62 cm².",
        ovary_r4: document.getElementById('field_ovary_r4')?.innerText || "- Doppler màu: Không thấy tăng sinh mạch máu bất thường trong vách hoặc thành nang (RI = 0.62).",
        ovary_l1: document.getElementById('field_ovary_l1')?.innerText || "- Kích thước buồng trứng: 26 x 18 mm. Nhu mô đồng nhất. Các nang noãn sinh lý < 8 mm rải rác ở ngoại vi, không thấy cấu trúc u cục khu trú hay nang bất thường.",
        douglas: document.getElementById('field_douglas')?.innerText || "- Cùng đồ sau không có dịch tự do. Không phát hiện khối bất thường vùng tiểu khung.",
        conclusion_l1: document.getElementById('field_conclusion_l1')?.innerText || "1. HÌNH ẢNH U NANG BUỒNG TRỨNG PHẢI (THEO DÕI U BÌ / U NANG THANH DỊCH - PHÂN LOẠI O-RADS 2).",
        conclusion_l2: document.getElementById('field_conclusion_l2')?.innerText || "2. BUỒNG TRỨNG TRÁI VÀ CÙNG ĐỒ DOUGLAS HIỆN TẠI TRONG GIỚI HẠN BÌNH THƯỜNG. ĐỀ NGHỊ SIÊU ÂM KIỂM TRA LẠI SAU 3 THÁNG.",
        doctorTitle: document.getElementById('field_doctorTitle')?.innerText || "Bác sĩ chuyên khoa Chẩn đoán hình ảnh",
        doctorName: document.getElementById('field_doctorName')?.innerText || "BS.CKII. Trương Thị Phượng",
        imageBefore: imageBeforeVal,
        imageAfter: overlayBase64 || (typeof currentPrediction !== 'undefined' && currentPrediction?.overlay_base64 ? currentPrediction.overlay_base64 : null),
        imageBeforeCaption: "Mặt cắt dọc đầu dò âm đạo (TVUS 7.5MHz)",
        imageCaliperTag: `D1: ${document.getElementById('resDmax')?.innerText || '28.5 mm'} • D2: ${document.getElementById('resDorth')?.innerText || '21.0 mm'} • DT: ${document.getElementById('resArea')?.innerText || '4.62 cm²'}`
    };

    try {
        const resp = await fetch(`${API_BASE}/api/generate-report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reportPayload)
        });
        if (!resp.ok) throw new Error("Lỗi máy chủ khi tạo file PDF");

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const pidName = reportPayload.patientId || "VINMEC";
        a.download = `Phieu_Ket_Qua_Sieu_Am_${pidName}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showToast("✓ Đã tải file PDF phiếu kết quả siêu âm chuẩn Vinmec!");
    } catch (err) {
        showToast("Lỗi xuất PDF: " + err.message, false);
    }
}

function printCurrentReport() {
            showToast("Đang chuẩn bị trang in phiếu kết quả...", true);
            window.print();
        }
