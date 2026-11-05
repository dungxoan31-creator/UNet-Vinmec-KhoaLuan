# Source evidence snapshot

Line numbers correspond to the current dirty worktree on 2026-11-04. No remediation applied.

## AUD-001 — backend/services/patient_identity.py:28

```text
25:             return existing_synthetic
26:
27:     secret = patient_pid_secret()
28:     digest = patient_id_digest(source_id, secret)
29:     key_id = patient_pid_key_id(secret)
30:     db.execute(
31:         sqlite_insert(PatientModel)
32:         .values(
33:             id=str(uuid.uuid4()),
34:             anonymized_pid=new_synthetic_patient_id(),
35:             source_pid_hmac=digest,
36:             pid_hmac_key_id=key_id,
37:             age_bucket=age_bucket or None,
38:         )
39:         .on_conflict_do_nothing(index_elements=[PatientModel.source_pid_hmac])
40:     )
41:     patient = db.query(PatientModel).filter_by(source_pid_hmac=digest).first()
42:     if patient is None or patient.pid_hmac_key_id != key_id:
```

## AUD-002 — backend/app/routers/admin.py:1394

```text
1391:
1392:
1393: @router.put("/api/admin/settings")
1394: def update_admin_settings(settings: AdminSettingsRequest):
1395:     """Update admin workspace settings."""
1396:     updated_settings = {**_ADMIN_SETTINGS, **settings.model_dump(exclude_unset=True)}
1397:     try:
1398:         _save_admin_settings(updated_settings)
1399:     except OSError as exc:
1400:         raise HTTPException(status_code=500, detail="Không thể lưu cấu hình quản trị.") from exc
1401:     _ADMIN_SETTINGS.clear()
1402:     _ADMIN_SETTINGS.update(updated_settings)
1403:     return {"status": "SUCCESS", "message": "Đã lưu cấu hình.", "settings": _ADMIN_SETTINGS}
1404:
1405:
1406: @router.get("/api/admin/metadata")
1407: def get_admin_metadata(db: Session = Depends(get_db)):
1408:     """Return administrative system metadata and summary statistics."""
```

## AUD-003 — backend/app/routers/admin.py:643

```text
640:
641:
642: @router.post("/api/admin/backups/create")
643: def trigger_backup(db: Session = Depends(get_db)):
644:     """
645:     Creates a database-only backup; admin routes do not package patient images.
646:     """
647:     from backend.services.backup_service import BackupService
648:
649:     backup_service = BackupService()
650:     result = backup_service.create_backup(include_images=False)
651:     return {
652:         key: result[key]
653:         for key in ("status", "backup_filename", "size_mb", "timestamp", "included_images", "encryption")
654:         if key in result
655:     }
656:
657:
```

## AUD-003 — backend/services/backup_service.py:78

```text
75:             src_conn = connect_sqlite(self.db_path)
76:             dest_conn = connect_sqlite(dest_db_path)
77:             with dest_conn:
78:                 src_conn.backup(dest_conn, pages=100)
79:             dest_conn.close()
80:             src_conn.close()
81:
82:             # 2. Copy media directories if requested
83:             if include_images and os.path.exists(self.data_dir):
84:                 dest_data_dir = os.path.join(temp_backup_dir, "data")
85:                 shutil.copytree(
86:                     self.data_dir,
87:                     dest_data_dir,
88:                     dirs_exist_ok=True,
89:                     ignore=shutil.ignore_patterns("*.tmp", "*.lock"),
90:                 )
91:
92:             # 3. Create compressed tar.gz archive
```

## AUD-004 — frontend/app/intake.js:152

```text
149:             dialog.close();
150:             renderList();
151:           } else {
152:             patientsStore.add(patientsKey(), patient);
153:             toast("Đã tạo hồ sơ bệnh nhân.");
154:             dialog.close();
155:             open(patient);
156:           }
157:         });
158:
159:       const d = document.querySelector("#modal");
160:       if (d) {
161:         const birthYearInput = d.querySelector('[name="birth_year"]');
162:         const agePreview = d.querySelector("#agePreview");
163:         if (birthYearInput && agePreview) {
164:           birthYearInput.addEventListener("input", () => {
165:             const res = validateBirthYear(birthYearInput.value, currentYear);
166:             agePreview.textContent = res.valid ? `(${res.age} tuổi)` : "";
```

## AUD-005 — frontend/app/intake.js:22

```text
19: } from "./form-validator.js";
20:
21: const patientsKey = () => `ova.demo-patients.v1.${encodeURIComponent(state.user?.id ?? "anonymous")}`;
22: const patientsStore = createDemoPatientStore([
23:   { pid: "100000001", name: "Nguyễn Minh Anh", age: 32 },
24:   { pid: "100000002", name: "Trần Thu Hà", age: 41 },
25:   { pid: "100000003", name: "Lê Ngọc Mai", age: 28 },
26:   { pid: "100000004", name: "Phạm Thanh Vy", age: 36 },
27: ]);
28: const readPatients = () => {
29:
30:   const rows = patientsStore.read(patientsKey()).map(row => /^DEMO-SYNTHETIC-\d{4}$/.test(row.pid)
31:     ? { ...row, pid: String(900000000 + Number(row.pid.slice(-4))), synthetic: true }
32:     : { ...row, synthetic: row.synthetic === true || DEMO_PATIENTS.some(seed => seed.pid === row.pid && seed.name === row.name) });
33:   const ids = new Set(rows.map(row => row.pid));
34:   const syntheticMode = state.capabilities?.synthetic_demo_mode === true;
35:   const additions = syntheticMode ? DEMO_PATIENTS.filter(row => !ids.has(row.pid)) : [];
36:   const all = patientsStore.save(patientsKey(), [...rows, ...additions]);
```

## AUD-006 — frontend/app/personal.js:65

```text
62:           if (data.new_password !== data.confirmation)
63:             return toast("Mật khẩu xác nhận không trùng.", true);
64:           try {
65:             await request("/api/auth/change-password", {
66:               method: "POST",
67:               body: data,
68:             });
69:             d.close();
70:             toast("Đã đổi mật khẩu.");
71:           } catch (err) {
72:             toast(err.message, true);
73:           }
74:         },
75:       );
76:   } else if (route === "preferences") {
77:     root.innerHTML =
78:       pageHead("Tùy chọn", "Lưu riêng trên thiết bị này.") +
79:       `<section class="panel"><form id="preferencesForm" class="panel-body" style="max-width:560px"><label class="field">Giao diện<select name="theme"><option value="system">Theo màn hình: quản lý sáng, workstation tối</option><option value="light">Sáng</option><option value="dark">Tối</option></select></label><label class="field">Ngôn ngữ<select name="language"><option value="vi">Tiếng Việt</option><option value="en">English – điều hướng</option></select></label><label class="field">Bố cục viewer<select name="layout"><option value="single">Một ảnh</option><option value="side">Song song với ảnh gốc</option></select></label><button class="btn primary" type="submit">Lưu tùy chọn</button></form></section>`;
```

## AUD-007 — backend/db/database.py:900

```text
897:                     user.is_global_admin = True
898:                 # DO NOT automatically guess or backfill facility_id for existing legacy accounts
899:                 if os.environ.get(password_key):
900:                     user.password_hash = hash_password(os.environ[password_key])
901:             elif not user and os.environ.get(password_key):
902:                 db.add(UserModel(
903:                     id=str(uuid.uuid4()), username=username, role=role,
904:                     full_name=os.environ.get(name_key) or label, title="",
905:                     facility_id=os.environ.get("APP_DOCTOR_FACILITY_ID") if role == "DOCTOR" else None,
906:                     is_global_admin=True if role == "ADMIN" and not os.environ.get("APP_DOCTOR_FACILITY_ID") else False,
907:                     password_hash=hash_password(os.environ[password_key]),
908:                     is_active=True,
909:                 ))
910:         db.commit()
911:
912:     try:
913:         dialect_name = "PostgreSQL" if engine.dialect.name == "postgresql" else "SQLite"
914:         print(f"[Database] {dialect_name} DB initialized and verified.")
```

## AUD-008 — frontend/app/intake-session.js:82

```text
79:     return copy;
80:   };
81:   const read = (key) => {
82:     if (memory.has(key)) return memory.get(key).map(row => ({ ...row }));
83:     try {
84:       const rows = JSON.parse(storage().getItem(key));
85:       if (Array.isArray(rows) && rows.length && rows.every(row =>
86:         row && typeof row.pid === "string" && typeof row.name === "string" &&
87:         Number.isFinite(row.age))) {
88:         memory.set(key, rows);
89:         return rows.map(row => ({ ...row }));
90:       }
91:     } catch {}
92:     return save(key, seeds);
93:   };
94:   return {
95:     read,
96:     save,
```

## AUD-009 — frontend/app/intake-session.js:85

```text
82:     if (memory.has(key)) return memory.get(key).map(row => ({ ...row }));
83:     try {
84:       const rows = JSON.parse(storage().getItem(key));
85:       if (Array.isArray(rows) && rows.length && rows.every(row =>
86:         row && typeof row.pid === "string" && typeof row.name === "string" &&
87:         Number.isFinite(row.age))) {
88:         memory.set(key, rows);
89:         return rows.map(row => ({ ...row }));
90:       }
91:     } catch {}
92:     return save(key, seeds);
93:   };
94:   return {
95:     read,
96:     save,
97:     get(key, pid) {
98:       const rows = read(key);
99:       const row = rows.find(r => r.pid === pid);
```

## AUD-010 — frontend/app/intake-session.js:74

```text
71:     const copy = rows.map(row => ({ ...row }));
72:     memory.set(key, copy);
73:     try {
74:       storage().setItem(key, JSON.stringify(copy));
75:       transient.delete(key);
76:     } catch {
77:       transient.add(key);
78:     }
79:     return copy;
80:   };
81:   const read = (key) => {
82:     if (memory.has(key)) return memory.get(key).map(row => ({ ...row }));
83:     try {
84:       const rows = JSON.parse(storage().getItem(key));
85:       if (Array.isArray(rows) && rows.length && rows.every(row =>
86:         row && typeof row.pid === "string" && typeof row.name === "string" &&
87:         Number.isFinite(row.age))) {
88:         memory.set(key, rows);
```

## AUD-010 — frontend/app/auth.js:45

```text
42:     .catch(() => {});
43:   location.hash = state.mustChangePassword ? "#first" : "#dashboard";
44: }
45: export async function logout() {
46:   clearActive();
47:   try {
48:     if (state.token)
49:       await request("/api/auth/logout", { method: "POST", signal: null, timeoutMs: 5000 });
50:   } catch {
51:     toast("Trình duyệt đã xóa phiên, nhưng máy chủ chưa xác nhận thu hồi token.", true);
52:   } finally {
53:     state.user = null;
54:     state.token = null;
55:     state.mustChangePassword = false;
56:     sessionStorage.removeItem("ova.token");
57:     sessionStorage.removeItem("ova.expiry");
58:     location.hash = "#login";
59:   }
```

## AUD-011 — frontend/app/intake.js:106

```text
103:         field("Họ và tên", "full_name", "text", existingPatient?.name || "", 'required maxlength="120"') +
104:         field("Số CCCD / Hộ chiếu", "national_id", "text", existingPatient?.national_id || "", 'maxlength="20" placeholder="12 số CCCD hoặc số Hộ chiếu"') +
105:         `<label class="field"><span>Năm sinh <span class="age-badge-preview" id="agePreview">${initialAgeText}</span></span><input name="birth_year" type="number" value="${esc(initialBirthYear)}" required min="1900" max="${currentYear}"></label>` +
106:         field("Số điện thoại", "phone", "tel", existingPatient?.phone || "", 'required maxlength="24"') +
107:         `<label class="field">Giới tính<select name="gender" required>
108:           <option value="">Chọn giới tính</option>
109:           <option value="female"${existingPatient?.gender === "female" ? " selected" : ""}>Nữ</option>
110:           <option value="male"${existingPatient?.gender === "male" ? " selected" : ""}>Nam</option>
111:           <option value="other"${existingPatient?.gender === "other" ? " selected" : ""}>Khác</option>
112:           <option value="unknown"${existingPatient?.gender === "unknown" ? " selected" : ""}>Không muốn nêu</option>
113:         </select></label>` +
114:         field("Quê quán", "hometown", "text", existingPatient?.hometown || "", 'required maxlength="120"') +
115:         '<p class="form-error" data-patient-error role="alert" hidden></p><div class="actions"><button class="btn" value="cancel">Hủy</button><button class="btn primary" type="submit">' + submitText + '</button></div>',
116:         (event, dialog) => {
117:           if (!active()) return dialog.close();
118:           const data = Object.fromEntries(new FormData(event.target));
119:           const pidVal = validatePid(currentPid, { existingPids: readPatients().map(p => p.pid), currentPid: isEditing ? currentPid : null });
120:           const nameVal = validateFullName(data.full_name);
```

## AUD-011 — frontend/app/upload.js:186

```text
183:       const result = metadata.prepared_case || await request("/api/cases", {
184:         method: "POST",
185:         body: {
186:           patient_id: targetPid && targetPid.trim() ? targetPid.trim() : null,
187:           active_ovary_side: activeOvarySide,
188:           contralateral_status: contralateralStatus || "UNKNOWN",
189:           clinical_notes: state.capabilities?.synthetic_demo_mode === true ? null : metadata.reason,
190:           study_date: metadata.study_date,
191:         },
192:         headers: metadata.idempotency_key
193:           ? { "Idempotency-Key": metadata.idempotency_key }
194:           : {},
195:         signal,
196:       });
197:       check();
198:       pending = {
199:         ...result,
200:         owner: identity,
```

## AUD-013 — frontend/css/workspace.css:2763

```text
2760: .intake-images progress { width: 100%; height: 6px; }
2761: .intake-side-confirm { display: flex; align-items: flex-start; gap: 8px; padding: 8px 0; font-size: 13px; }
2762: .intake-side-confirm input { flex: none; margin-top: 3px; }
2763: .intake-action-bar {
2764:   position: sticky; bottom: 40px; z-index: 20;
2765:   display: flex; justify-content: space-between; align-items: center; gap: 16px;
2766:   padding: 12px 16px; margin-top: 16px; background: var(--surface);
2767:   border: 1px solid var(--border); border-radius: var(--radius-lg);
2768: }
2769: .intake-action-bar p { margin: 0; flex: 1; }
2770: .intake-action-bar .btn { flex-shrink: 0; white-space: normal; }
2771: body:has(.intake-workspace) #toasts { top: 76px; bottom: auto; pointer-events: none; }
2772: .intake-workspace :is(input, button, select, summary) { scroll-margin-bottom: 150px; scroll-margin-top: 85px; }
2773: #reviewContentWarning { display: block; }
2774: #reviewContentWarning p { margin: 0 0 8px; }
2775: #reviewContentWarning label { display: block; }
2776: .intake-side-confirm[hidden], #reviewContentWarning[hidden], #reviewContentAckLabel[hidden] { display: none; }
2777: @media (max-width: 800px) {
```

## AUD-014 — frontend/app/intake.js:253

```text
250:   autofillState.reset(); root.classList.add("intake-workspace");
251:   root.innerHTML = `<div class="intake-identity banner info"><div><strong>${esc(patient.name)}</strong> · PID: <span class="mono">${esc(patient.pid || "Chưa cấp")}</span> · Visit No <span class="mono" data-visit-no aria-live="polite">Chưa cấp</span> ${button("Tạo Visit", "create-visit", "small")}</div>${button("Chọn bệnh nhân khác", "change-patient", "small")}</div>` +
252:     pageHead("Khảo sát buồng trứng", "Kiểm tra mã ca, ảnh và bên. Có thể khảo sát một hoặc hai bên.") + storageNotice() +
253:     `<section class="panel intake-metadata"><div class="panel-body grid-2">${pidField}
254:       <label class="field">Ngày giờ khảo sát<div class="intake-date"><input type="datetime-local" name="study-date" value="${nowLocal()}" required>${button("Hiện tại", "set-now", "small")}</div></label>
255:       ${reasonField}
256:       <div id="metadataProposals" class="intake-metadata-proposals" role="status" aria-live="polite"></div></div></section>
257:     <details class="intake-privacy"><summary>Không tải ảnh có chữ định danh. Thông tin bảo mật và dữ liệu nguồn</summary><p class="small muted">Máy chủ lưu PID giả danh và dấu HMAC thay cho PID nguồn. DICOM chưa được khử định danh đầy đủ: máy chủ lọc metadata văn bản, ngày giờ và thay UID nguồn; pixel không được làm sạch hay rà soát. Cờ BurnedInAnnotation từ máy siêu âm không xác nhận ảnh sạch; không tải ảnh có chữ định danh. Metadata chỉ là gợi ý; không thay giá trị đã nhập nếu chưa được bác sĩ áp dụng.</p></details>
258:     <div class="actions intake-swap">${button("Đổi bên ảnh (Trái ⇄ Phải)", "swap-sides", "small", "refresh")}</div>
259:     <div class="grid-2 intake-images">${["L", "R"].map(side => `<section class="upload-card side-${side}"><h2><span class="badge side-${side}">${side === "L" ? "T" : "P"}</span>Buồng trứng ${side === "L" ? "trái (L)" : "phải (R)"}</h2>
260:       <div class="dropzone" data-side="${side}">${icon("upload", 24)}<p>Kéo thả ảnh vào bên ${side === "L" ? "trái" : "phải"}</p><small class="muted">Tối đa 20 ảnh · PNG, JPG, JPEG, DICOM · tối đa 20 MB/ảnh</small><label class="btn small">Chọn ảnh ${side === "L" ? "trái" : "phải"}<input type="file" data-file="${side}" accept=".png,.jpg,.jpeg,.dcm" multiple class="visually-hidden"></label></div>
261:       <div id="files-${side}" class="intake-file-list" aria-live="polite"><p class="small muted">Chưa chọn ảnh</p></div>
262:       <label class="intake-side-unavailable"><input type="checkbox" data-unavailable="${side}"> Đã phẫu thuật cắt bỏ / Không khảo sát được</label>
263:       <label class="field small" data-unavailable-wrap="${side}" hidden><span>Tình trạng bên không có ảnh</span><select data-unavailable-status="${side}" disabled><option value="">Chọn tình trạng</option><option value="SURGICALLY_ABSENT">Đã phẫu thuật cắt bỏ</option><option value="NOT_VISUALIZED">Không quan sát được</option></select></label>
264:       <progress id="progress-${side}" max="100" value="0" aria-label="Tiến trình tải ảnh ${side}"></progress><p id="stage-${side}" class="small" role="status">Chờ ảnh</p></section>`).join("")}</div>
265:     <div class="stepper"><span class="current"><b>1</b>Tải ảnh</span><span><b>2</b>Kiểm tra chất lượng</span><span><b>3</b>Phân đoạn</span><span><b>4</b>Đo kích thước</span></div>
266:     <div id="intakeError" role="alert"></div><div class="actions intake-recovery">${button("Thử lại quá trình", "retry-upload")}${button("Dừng chờ phản hồi", "cancel-upload")}</div>
267:     <div class="intake-action-bar"><p class="small" id="intakeHint" role="status">Chọn ít nhất một ảnh siêu âm.</p><button type="button" class="btn primary" id="startSegmentationBtn" data-action="start-segmentation" aria-describedby="intakeHint" disabled>${icon("arrow")} Phân tích ảnh AI</button></div>`;
```

## AUD-015 — frontend/app/intake.js:58

```text
55:     root.innerHTML = pageHead("Bắt đầu khảo sát", "Chọn hồ sơ có sẵn hoặc bắt đầu ca nghiên cứu không định danh.",
56:       (state.capabilities?.synthetic_demo_mode === true ? "" : button("Khảo sát không định danh", "anonymous-study", "primary")) +
57:       button("Tạo bệnh nhân", "add-patient", "small", "plus")) + storageNotice() +
58:       `<section class="panel"><div class="panel-head"><h2>Danh sách bệnh nhân</h2><span class="badge">${patients.length} hồ sơ</span></div><div class="table-wrap intake-patient-list" role="region" aria-label="Danh sách bệnh nhân" tabindex="0"><table><thead><tr><th>Mã bệnh nhân (PID)</th><th>Bệnh nhân</th><th>Tuổi</th><th>Thao tác</th></tr></thead><tbody>${patients.map((p, i) => `<tr><td class="mono">${esc(p.pid)}</td><td><strong>${esc(p.name)}</strong>${p.national_id ? `<br><small class="muted mono">CCCD/HC: ${esc(p.national_id)}</small>` : ""}</td><td>${p.age} tuổi</td><td><div class="table-actions-compact"><button class="btn small primary" type="button" data-select="${i}">Chọn bệnh nhân</button><button class="btn small icon-only" type="button" data-edit-patient="${esc(p.pid)}" title="Sửa thông tin bệnh nhân" aria-label="Sửa thông tin ${esc(p.name)}">${icon("edit", 16)}</button><button class="btn small danger icon-only" type="button" data-delete-patient="${esc(p.pid)}" title="Xóa bệnh nhân" aria-label="Xóa hồ sơ ${esc(p.name)}">${icon("trash", 16)}</button></div></td></tr>`).join("")}</tbody></table></div></section>`;
59:     const table = root.querySelector('.intake-patient-list');
60:     table.insertAdjacentHTML('beforebegin', `<label class="field">Tìm theo tên hoặc mã hồ sơ<input id="patientSearch" type="search" placeholder="Nhập tên có dấu hoặc không dấu" value="${esc(search)}"></label>`);
61:     root.querySelector('.panel .badge').textContent = `${filtered.length} / ${allPatients.length} hồ sơ`;
62:     table.insertAdjacentHTML('afterend', `<div class="actions"><button type="button" class="btn small" id="patientPrev" ${page === 0 ? 'disabled' : ''}>Trang trước</button><span role="status">Trang ${page + 1} / ${pageCount}</span><button type="button" class="btn small" id="patientNext" ${page + 1 >= pageCount ? 'disabled' : ''}>Trang sau</button></div>`);
63:     if (!patients.length) table.insertAdjacentHTML('afterbegin', '<p class="muted">Không tìm thấy hồ sơ phù hợp.</p>');
64:     root.querySelector('#patientSearch').oninput = event => {
65:       search = event.target.value; page = 0;
66:       renderList();
67:       root.querySelector('#patientSearch').focus();
68:     };
69:     root.querySelector('#patientPrev').onclick = () => { page--; renderList(); };
70:     root.querySelector('#patientNext').onclick = () => { page++; renderList(); };
71:     const open = patient => {
72:       if (!active()) return;
```

## AUD-016 — frontend/app/report-preview.js:381

```text
378:   return match ? `${match[3]}/${match[2]}/${match[1]}` : value || "Chưa ghi nhận";
379: }
380:
381: function reportSideOverview(images, side) {
382:   const summary = images.length
383:     ? `<p>${images.length} ảnh tĩnh đã được gắn với bên này. Số đo và nhận định được liệt kê riêng theo từng ảnh ở các trang hình ảnh.</p>`
384:     : '<p class="report-missing-side">Chưa có ảnh khảo sát bên này.</p>';
385:   return `<section class="report-result-side"><h3>${esc(reportSideName(side))}</h3>${summary}</section>`;
386: }
387:
388: function reportEvidenceSide(entries, side) {
389:   if (!entries.length) {
390:     return `<section class="report-evidence-side"><h3>${esc(reportSideName(side))}</h3><p class="report-missing-side">Chưa có ảnh khảo sát bên này.</p></section>`;
391:   }
392:
393:   const evidence = entries
394:     .map(({ image, assets, imageNumber }, index) => {
395:       const itemLabel = `<p class="report-entry-index">Ảnh ${imageNumber || index + 1}</p>`;
```

## AUD-017 — frontend/app/admin.js:68

```text
65:       return await renderMetadata(target);
66:     } else if (section === "settings") {
67:       const config = await request("/api/admin/settings");
68:       target.innerHTML = `<section class="panel"><form id="settingsForm" class="panel-body" style="max-width:600px"><p class="muted small">Chất lượng ảnh được kiểm tra bằng các quy tắc kỹ thuật cố định; cấu hình này không thay đổi ngưỡng đánh giá.</p>${field("Tên đơn vị trên phiếu", "report_header", "text", config.report_header, "required")}<label class="field">Đơn vị<select name="unit"><option value="auto">Theo hiệu chuẩn; thiếu spacing chỉ dùng pixel</option></select></label><button class="btn primary" type="submit">Lưu cấu hình</button></form></section>`;
69:       $("#settingsForm").onsubmit = async (e) => {
70:         e.preventDefault();
71:         const data = Object.fromEntries(new FormData(e.target));
72:         try {
73:           {
74:             await request("/api/admin/settings", { method: "PUT", body: data });
75:           }
76:           toast("Đã lưu cấu hình" + ".");
77:         } catch (e) {
78:           toast(e.message, true);
79:         }
80:       };
81:     } else {
82:       const data = await request("/api/health");
```

## AUD-017 — frontend/app/report-preview.js:469

```text
466:   return `<article class="report" aria-label="Kết quả khảo sát buồng trứng">
467:     <section class="report-page report-summary-page">
468:       <header class="report-header">
469:         <h1>KẾT QUẢ KHẢO SÁT</h1>
470:       </header>
471:       ${RUO_REPORT_DISCLOSURE}
472:       ${syntheticDemoDisclosure}
473:       <div class="report-patient-line"><p>PID: <strong>${esc(study.patient_id || "Chưa ghi nhận")}</strong></p><p>Visit: <strong>${esc(visitNumber)}</strong></p><p>Ngày khảo sát: <strong>${esc(reportDate(study.study_date))}</strong></p></div>
474:
475:       <section class="report-block report-case-block">
476:         <h2>THÔNG TIN CA</h2>
477:         <dl><div><dt>Mã ca</dt><dd>${esc(caseCode)}</dd></div><div><dt>Trạng thái lưu rà soát</dt><dd>${esc(status)}</dd><small>Trạng thái lưu phản ánh dữ liệu rà soát; mô tả, O-RADS và kết luận được quản lý riêng.</small></div></dl>
478:       </section>
479:
480:       <section class="report-block report-results-block">
481:         <h2>KẾT QUẢ GHI NHẬN</h2>
482:         <div class="report-results-grid">${reportSideOverview(sides.L.map(({ image }) => image), "L")}${reportSideOverview(sides.R.map(({ image }) => image), "R")}</div>
483:         ${sides.U.length ? `<div class="report-unassigned">${reportSideOverview(sides.U.map(({ image }) => image), "U")}</div>` : ""}
```

## AUD-019 — backend/app/routers/admin.py:315

```text
312:     total_predictions = pred_query.count()
313:
314:     avg_iqa_val = pred_query.with_entities(func.avg(PredictionModel.iqa_score)).filter(PredictionModel.iqa_score.isnot(None)).scalar()
315:     avg_iqa_score = round(float(avg_iqa_val), 3) if avg_iqa_val is not None else 0.0
316:     pass_iqa_count = pred_query.filter(PredictionModel.iqa_score >= 0.5).count()
317:     iqa_pass_rate_pct = round((pass_iqa_count / total_predictions) * 100.0, 1) if total_predictions > 0 else 0.0
318:
319:     preds_all = pred_query.all()
320:     iqa_tiers = {
321:         "Xuất sắc (≥ 0.8)": sum(1 for p in preds_all if p.iqa_score and p.iqa_score >= 0.8),
322:         "Đạt chuẩn (0.5 - 0.8)": sum(1 for p in preds_all if p.iqa_score and 0.5 <= p.iqa_score < 0.8),
323:         "Cần chú ý (< 0.5)": sum(1 for p in preds_all if p.iqa_score is not None and p.iqa_score < 0.5),
324:     }
325:
326:     rev_query = db.query(ReviewModel)
327:     if matched_image_ids:
328:         rev_query = rev_query.filter(ReviewModel.image_id.in_(matched_image_ids))
329:     elif total_images == 0:
```

## AUD-019 — backend/app/routers/admin.py:345

```text
342:     }
343:
344:     avg_dur = rev_query.with_entities(func.avg(ReviewModel.time_spent_seconds)).filter(ReviewModel.time_spent_seconds > 0).scalar()
345:     avg_review_seconds = round(float(avg_dur), 1) if avg_dur is not None else 0.0
346:
347:     active_docs = rev_query.with_entities(ReviewModel.doctor_id).distinct().count()
348:
349:     orads_distribution = {
350:         "O-RADS 1": 0,
351:         "O-RADS 2": 0,
352:         "O-RADS 3": 0,
353:         "O-RADS 4": 0,
354:         "O-RADS 5": 0,
355:         "Chưa ghi nhận": 0,
356:     }
357:     for (fb,) in rev_query.with_entities(ReviewModel.hitl_feedback).all():
358:         if isinstance(fb, dict):
359:             val = str(fb.get("orads") or fb.get("orads_score") or "").upper().strip()
```

## AUD-020 — frontend/app/viewer.js:42

```text
39: import { reviewWarnings, consistencyKey } from "./review-content.js";
40: let active = null;
41: const ORADS1_OPTION_LABEL =
42:   "O-RADS 1 - Không có tổn thương hoặc nang sinh lý do bác sĩ xác định (nang noãn < 30 mm; hoàng thể thường ≤ 30 mm)";
43: const ORADS0_OPTION_LABEL =
44:   "O-RADS 0 - Đánh giá chưa đầy đủ do yếu tố kỹ thuật (chưa phân tầng nguy cơ)";
45: export function currentViewer() {
46:   return active;
47: }
48: export async function renderViewer(root, id, { readonly = false } = {}) {
49:   root.innerHTML = loading();
50:   let disposed = false,
51:     cleanup = () => {};
52:   try {
53:     const c = await openCase(id);
54:     if (!root.isConnected) return;
55:     if (restoreMaskDrafts(c).length) {
56:       toast("Đã phục hồi bản nháp chưa lưu gần nhất");
```

## AUD-020 — frontend/app/admin-reports.js:15

```text
12:     const oradsBadges = {
13:       "O-RADS 1": { color: "#10b981", label: "Sinh lý / Bình thường" },
14:       "O-RADS 2": { color: "#0284c7", label: "Lành tính cao (<1%)" },
15:       "O-RADS 3": { color: "#f59e0b", label: "Nguy cơ thấp (1-9%)" },
16:       "O-RADS 4": { color: "#ea580c", label: "Nguy cơ trung bình (10-49%)" },
17:       "O-RADS 5": { color: "#ef4444", label: "Nguy cơ cao (≥50%)" },
18:       "Chưa ghi nhận": { color: "#64748b", label: "Chờ rà soát" },
19:     };
20:
21:     const lesionColors = {
22:       "U quái (Dermoid cyst)": "#8b5cf6",
23:       "Nang lạc nội mạc tử cung (Chocolate cyst)": "#d946ef",
24:       "U nang tuyến thanh dịch": "#0284c7",
25:       "U nang tuyến nhầy": "#06b6d4",
26:       "Nang đơn giản": "#10b981",
27:       "U tế bào vỏ (Thecoma)": "#f59e0b",
28:       "Ung thư biểu mô thanh dịch độ cao": "#ef4444",
29:       "Buồng trứng bình thường": "#10b981",
```

## AUD-021 — frontend/app/admin-reports.js:409

```text
406:                   const pct = Math.round((count / totalOradsCount) * 100);
407:                   const isSelected = state.chartFilter.type === "ORADS" && state.chartFilter.value === key;
408:                   return `
409:                     <div class="chart-drilldown-row" data-orads="${esc(key)}" style="cursor:pointer; padding:6px 8px; border-radius:6px; border:1px solid ${isSelected ? "#0284c7" : "transparent"}; background:${isSelected ? "#f0f9ff" : "transparent"}; transition:all 0.15s ease;" title="Bấm để lọc ca ${esc(key)}">
410:                       <div style="display:flex; justify-content:space-between; margin-bottom:3px; font-size:12.5px;">
411:                         <span style="font-weight:600; display:inline-flex; align-items:center; gap:6px;">
412:                           <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${badge.color};"></span>
413:                           ${esc(key)} <small class="muted" style="font-weight:400;">(${esc(badge.label)})</small>
414:                         </span>
415:                         <span style="font-weight:700;">${count} ca (${pct}%)</span>
416:                       </div>
417:                       <div style="background:#e2e8f0; height:7px; border-radius:4px; overflow:hidden;">
418:                         <div style="width:${pct}%; background:${badge.color}; height:100%;"></div>
419:                       </div>
420:                     </div>
421:                   `;
422:                 }).join("")}
423:               </div>
```

## AUD-022 — frontend/app/review.js:259

```text
256:         state.lastReviewTimeSpent = null;
257:         c.status = "REVIEWED";
258:         notifyReviewDraftStateChanged();
259:         toast("Đã lưu rà soát của hai bên thành công.");
260:       } else {
261:         // Retain unpersisted edits made after snapshot
262:         state.dirty = true;
263:         c.status = "REVIEWED";
264:         notifyReviewDraftStateChanged();
265:         toast("Đã lưu bản rà soát trước đó. Có thay đổi mới chưa lưu.");
266:       }
267:     }
268:
269:     // The committed review is the clinical write. Keep telemetry queued/retryable
270:     // without holding the viewer's save lock on a separate network request.
271:     void flushReviewAcknowledgements();
272:     return { status: "saved", studyId: c.study_id, revision: c.review_revision, clean: !state.dirty };
273:   } catch (e) {
```

## AUD-023 — frontend/app/api.js:34

```text
31:     if (!signal?.aborted && controller.signal.aborted) {
32:       throw new ApiError("Máy chủ phản hồi quá lâu. Vui lòng thử lại.", 408);
33:     }
34:     throw error;
35:   } finally {
36:     clearTimeout(timer);
37:     signal?.removeEventListener("abort", abortFromCaller);
38:   }
39: }
40:
41: export async function request(
42:   path,
43:   {
44:     method = "GET",
45:     body,
46:     signal = state.routeController?.signal,
47:     timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
48:     headers: requestHeaders = {},
```

## AUD-024 — evaluation/selected_model.json:11

```text
8:   "threshold": 0.4,
9:   "horizontal_flip_tta": true,
10:   "decoder_attention_type": "scse",
11:   "loss_function": "AdvancedHybridLoss(0.5 FocalTversky + 0.3 SoftDice + 0.2 BCE)",
12:   "pretraining_source": "MMOTU 2D Ovarian Ultrasound (1000 pairs, zero-shot transfer)",
13:   "input_normalization": {
14:     "mean": 0.449,
15:     "std": 0.226
16:   },
17:   "inference_protocol": {
18:     "decode": "OpenCV IMREAD_GRAYSCALE",
19:     "input_channels": 1,
20:     "letterbox_size": [
21:       512,
22:       512
23:     ],
24:     "clahe_clip_limit": 2.0,
25:     "clahe_grid_size": [
```

## AUD-024 — ai_training/train_unetplusplus_resnet34.py:172

```text
169:
170:     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
171:     model = build_model(pretrained=True).to(device)
172:     criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
173:     optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
174:     scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
175:     scaler = torch.amp.GradScaler(device.type, enabled=device.type == "cuda")
176:
177:     output_dir.mkdir(parents=True, exist_ok=True)
178:     best_path = output_dir / "unetplusplus_resnet34_best.pth"
179:     last_path = output_dir / "unetplusplus_resnet34_last.pth"
180:     history = []
181:     best_dice = -1.0
182:     best_epoch = 0
183:     no_improvement = 0
184:     started = time.perf_counter()
185:
186:     for epoch in range(1, epochs + 1):
```
