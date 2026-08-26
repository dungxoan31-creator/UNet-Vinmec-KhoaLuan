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
            if (!badge || !pointer) return;

            badge.className = 'orads-badge';
            if (pathology.includes('Normal') || pathology.includes('bình thường')) {
                badge.classList.add('orads-badge-1');
                badge.innerText = 'O-RADS 1 (Bình thường / 0%)';
                pointer.style.left = '10%';
            } else if (pathology.includes('Simple') || pathology.includes('thanh dịch')) {
                badge.classList.add('orads-badge-2');
                badge.innerText = 'O-RADS 2 (Lành tính <1%)';
                pointer.style.left = '30%';
            } else if (pathology.includes('Dermoid') || pathology.includes('U bì')) {
                badge.classList.add('orads-badge-2');
                badge.innerText = 'O-RADS 2 (U bì lành tính <1%)';
                pointer.style.left = '35%';
            } else if (pathology.includes('Endometrioma') || pathology.includes('lạc nội mạc')) {
                badge.classList.add('orads-badge-3');
                badge.innerText = 'O-RADS 3 (Nguy cơ thấp 1-10%)';
                pointer.style.left = '52%';
            } else if (pathology.includes('Hemorrhagic') || pathology.includes('xuất huyết')) {
                badge.classList.add('orads-badge-2');
                badge.innerText = 'O-RADS 2 (Lành tính <1%)';
                pointer.style.left = '30%';
            } else {
                badge.classList.add('orads-badge-4');
                badge.innerText = 'O-RADS 4 (Nguy cơ TB 10-50%)';
                pointer.style.left = '75%';
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
                has_solid_component: false,
                papillary_projections_count: 0,
                acoustic_shadowing: false,
                fluid_echogenicity: "anechoic",
                locules_count: 1,
                color_score: 1,
                has_ascites: false
            },
            patient_info: {
                patient_id: currentCase.patient_id || "BN-VINMEC",
                patient_age: currentCase.patient_age || "32",
                study_code: currentCase.study_code || "STD-01"
            },
            pathology_name: document.getElementById('selectPathology')?.value || "U nang thanh dịch buồng trứng"
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

            const payload = {
                image_id: currentCase.image_id,
                doctor_id: "BS. Nguyễn Văn A",
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
            currentFacilityKey = facKey;
            const fac = VINMEC_FACILITIES[facKey] || VINMEC_FACILITIES['times_city'];
            
            // Sync Header UI
            const headerSelect = document.getElementById('headerFacilitySelect');
            if (headerSelect) headerSelect.value = facKey;
            const modalSelect = document.getElementById('modal_facilitySelector');
            if (modalSelect) modalSelect.value = facKey;

            // Sync User Department Label in header
            const deptLabel = document.getElementById('headerUserDept');
            if (deptLabel) deptLabel.innerText = fac.name.replace('BỆNH VIỆN ĐA KHOA QUỐC TẾ ', '');

            // Update Report Sheet Header
            applyFacilityToReport(facKey);
            showToast(`✓ Đã đổi sang cơ sở: ${fac.name.replace('BỆNH VIỆN ĐA KHOA QUỐC TẾ ', '')}`);
        }

function onModalFacilityChange(facKey) {
            onGlobalFacilityChange(facKey);
        }

function applyFacilityToReport(facKey) {
            const fac = VINMEC_FACILITIES[facKey] || VINMEC_FACILITIES['times_city'];
            const hospName = document.getElementById('field_hospitalName');
            const deptName = document.getElementById('field_departmentName');
            const hospAddr = document.getElementById('field_hospitalAddress');
            const hospContact = document.getElementById('field_hospitalContact');

            if (hospName) hospName.innerText = fac.name;
            if (deptName) deptName.innerText = fac.dept;
            if (hospAddr) hospAddr.innerText = fac.addr;
            if (hospContact) hospContact.innerText = fac.tel;
        }

function populateReportSheet(caseObj, overrides = {}) {
            if (!caseObj) caseObj = currentCase;
            applyFacilityToReport(currentFacilityKey);

            const pid = overrides.pid || caseObj.patient_id || 'BN-VINMEC-9284';
            const name = overrides.name || caseObj.patient_name || 'Nguyễn Thị Phượng';
            const gender = overrides.gender || caseObj.patient_gender || 'Female / Nữ';
            const dob = overrides.dob || caseObj.patient_dob || '16-May-1991';
            const refDoc = overrides.refDoc || caseObj.referring_doctor || 'TS. BS. Lê Khắc Hiếu';
            const visitType = overrides.visitType || caseObj.visit_type || 'OPD Visit / 3090373';
            const orderDate = overrides.orderDate || caseObj.study_date || new Date().toISOString().split('T')[0];
            const clinicalDiag = overrides.clinicalDiag || caseObj.clinical_indication || 'Theo dõi u nang buồng trứng phải / Đau tức nhẹ vùng hạ vị';
            const docName = overrides.docName || currentUser.full_name || 'BS. Nguyễn Văn A';
            const docTitle = overrides.docTitle || currentUser.title || 'Bác sĩ chuyên khoa Chẩn đoán hình ảnh';

            // AI and Doctor Measurements
            const meas = currentPrediction ? (currentPrediction.measurements || {}) : {};
            const d1 = meas.max_diameter_mm !== undefined && meas.max_diameter_mm !== null ? (typeof meas.max_diameter_mm === 'number' ? meas.max_diameter_mm.toFixed(1) : meas.max_diameter_mm) : (document.getElementById('resDmax') ? document.getElementById('resDmax').innerText.replace(' mm', '') : '46.3');
            const d2 = meas.ortho_diameter_mm !== undefined && meas.ortho_diameter_mm !== null ? (typeof meas.ortho_diameter_mm === 'number' ? meas.ortho_diameter_mm.toFixed(1) : meas.ortho_diameter_mm) : (document.getElementById('resDorth') ? document.getElementById('resDorth').innerText.replace(' mm', '') : '34.7');
            const area = meas.total_area_cm2 !== undefined && meas.total_area_cm2 !== null ? (typeof meas.total_area_cm2 === 'number' ? meas.total_area_cm2.toFixed(2) : meas.total_area_cm2) : (document.getElementById('resArea') ? document.getElementById('resArea').innerText.replace(' cm²', '') : '12.01');
            const lesionType = document.getElementById('selectPathology') ? document.getElementById('selectPathology').value : 'U nang thanh dịch (Simple Cyst)';

            // Elements
            if (document.getElementById('field_patientId')) document.getElementById('field_patientId').innerText = pid;
            if (document.getElementById('field_patientName')) document.getElementById('field_patientName').innerText = name;
            if (document.getElementById('field_patientGender')) document.getElementById('field_patientGender').innerText = gender;
            if (document.getElementById('field_patientDob')) document.getElementById('field_patientDob').innerText = dob;
            if (document.getElementById('field_orderDate')) document.getElementById('field_orderDate').innerText = orderDate;
            if (document.getElementById('field_visitType')) document.getElementById('field_visitType').innerText = visitType;
            if (document.getElementById('field_referringDoctor')) document.getElementById('field_referringDoctor').innerText = refDoc;
            if (document.getElementById('field_completedDate')) document.getElementById('field_completedDate').innerText = orderDate;
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

            // Doctor Stamp
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
            if (document.getElementById('edit_ovaryR2')) document.getElementById('edit_ovaryR2').value = document.getElementById('field_ovary_r2').innerText;
            if (document.getElementById('edit_ovaryR3')) document.getElementById('edit_ovaryR3').value = document.getElementById('field_ovary_r3').innerText;
            if (document.getElementById('edit_ovaryR4')) document.getElementById('edit_ovaryR4').value = document.getElementById('field_ovary_r4').innerText;
            if (document.getElementById('edit_ovaryL2')) document.getElementById('edit_ovaryL2').value = document.getElementById('field_ovary_l2').innerText;
            if (document.getElementById('edit_douglas')) document.getElementById('edit_douglas').value = document.getElementById('field_douglas').innerText;
            if (document.getElementById('edit_conc1')) document.getElementById('edit_conc1').value = document.getElementById('field_conclusion_l1').innerText;
            if (document.getElementById('edit_conc2')) document.getElementById('edit_conc2').value = document.getElementById('field_conclusion_l2').innerText;
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
            closeCaseDetailModal();
            const firstImg = activeModalCase.images && activeModalCase.images[0] ? activeModalCase.images[0] : null;
            const review = firstImg ? firstImg.review : null;
            const pred = firstImg ? firstImg.prediction : null;

            populateReportSheet(activeModalCase, {
                pid: activeModalCase.patient_id,
                name: activeModalCase.patient_name || 'Nguyễn Thị Phượng',
                orderDate: activeModalCase.study_date,
                clinicalDiag: activeModalCase.clinical_indication,
                docName: review ? review.doctor_id : 'BS. Nguyễn Văn A',
                conc1: review ? `1. HÌNH ẢNH ${review.lesion_type.toUpperCase()} BUỒNG TRỨNG PHẢI (PHÂN LOẠI O-RADS 2).` : undefined
            });

            navigateTo('report_complete');
        }

async function downloadCurrentPdfReport() {
            showToast("Đang tạo phiếu báo cáo y tế PDF chuẩn Vinmec...", true);
            const overlayBase64 = canvas.toDataURL('image/png');

            const reportPayload = {
                anonymized_pid: currentCase.patient_id,
                study_date: currentCase.study_date,
                patient_age: currentCase.patient_age + " (Tuổi sinh đẻ)",
                doctor_name: "BS. Nguyễn Văn A (CKI CĐHA - Vinmec)",
                probe_type: "Siêu âm 2D đầu dò âm đạo (TVUS)",
                lesion_type: document.getElementById('selectPathology').value,
                clinical_notes: document.getElementById('textDoctorNotes').value,
                doctor_action: currentCase.doctor_action,
                overlay_base64: overlayBase64,
                measurements: currentPrediction ? currentPrediction.measurements : { max_diameter_mm: 32.4, ortho_diameter_mm: 24.1, total_area_cm2: 6.82 }
            };

            try {
                const resp = await fetch(`${API_BASE}/api/generate-report`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(reportPayload)
                });
                if (!resp.ok) throw new Error("Lỗi tải PDF");

                const blob = await resp.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Phieu_Ket_Qua_Sieu_Am_${currentCase.patient_id}.pdf`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                showToast("✓ Đã tải file PDF phiếu kết quả siêu âm!");
            } catch (err) {
                showToast("Lỗi xuất PDF: " + err.message, false);
            }
        }

function printCurrentReport() {
            showToast("Đang chuẩn bị trang in phiếu kết quả...", true);
            window.print();
        }
