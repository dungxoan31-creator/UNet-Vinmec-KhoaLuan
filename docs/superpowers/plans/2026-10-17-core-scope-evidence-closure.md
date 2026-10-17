# Core Segmentation and HITL Evidence Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Đây là continuation của plan 16/10, không phải yêu cầu triển khai lại 20 task.

**Goal:** Khép bằng chứng và các lỗi nghiệm thu ảnh hưởng segmentation/HITL trước 18/10, chuyển sang báo cáo/bảo vệ từ 19/10 theo đúng phạm vi người dùng xác nhận.

**Architecture:** Giữ model, FastAPI/SQLite, Workspace ES modules và evaluator đã triển khai. Dùng một policy nghiệm thu chung dựa trên artifact có provenance; tách clinician validation khỏi technical fallback và Test độc lập khỏi retrospective replay.

**Tech Stack:** Python/PyTorch/OpenCV, FastAPI/SQLAlchemy/SQLite, JavaScript ES modules, pytest, Node/Playwright, PowerShell hiện có; không thêm dependency.

**Spec:** `docs/superpowers/specs/2026-10-17-thesis-core-scope-design.md`; đọc cùng plan 16/10 và progress ledger hiện hành.

## Global Constraints

- Tên đề tài: “Xây dựng hệ thống hỗ trợ phân đoạn tổn thương trên ảnh siêu âm buồng trứng ứng dụng Deep Learning theo mô hình Human-in-the-Loop.”
- Phạm vi cốt lõi: Ảnh siêu âm → Preprocessing → Segmentation → Mask/Overlay → Doctor Review/Edit/Confirm → Đánh giá kết quả.
- Không dùng Test tuning; không giả Patient ID, clinician, nhãn chuyên gia, PASS hoặc thời gian thực nghiệm.
- Bác sĩ: thực hiện nếu tiếp cận được; nếu không có thì fallback kỹ thuật và giới hạn công khai.
- Sinh mô tả/chẩn đoán, LLM/VLM, Draft Report Suggestion, Dashboard mở rộng chỉ sau nghiệm thu lõi và còn thời gian.
- Giữ Letterbox 512×512, Combo Loss và checkpoint khóa; không sửa/xóa dữ liệu gốc, split hay artifact lịch sử.
- Working tree còn nhiều thay đổi ngoài scope; không reset, stage hàng loạt hoặc commit thay người dùng.
- Lượt này chỉ cập nhật spec/plan; các test và code sửa bên dưới là việc của lần thực thi tiếp theo.

## Review Focus

1. Session gắn role clinician nhưng không có hồ sơ người tham gia: quarantine khỏi clinician summary — C03.
2. Chỉ chạy bốn test file nhưng báo full regression: verifier phải ghi rõ selection và collect đủ suite — C04.
3. Report không có provenance nhưng dùng default hash/thời điểm/technical_count: null hoặc UNKNOWN, không tự điền — C02.
4. Full suite pass nhưng browser bị skip: không prototype_ready — C02/C04.
5. Thiếu bác sĩ nhưng fallback hợp lệ: clinician_validation=false; không tự chặn evaluation_complete nếu các gate bắt buộc khác thực sự đạt — C02.

## Hiện trạng và phương án lựa chọn

Khảo sát ngày 17/10, HEAD `25af869`. Các file T01–T20 đã được triển khai theo progress ledger; không coi chữ “complete” trong ledger là đã nghiệm thu mọi điều kiện. Bằng chứng đã đọc: `evaluation/milestone_3_final/report/{release_status.json,pytest.txt,release_e2e.txt}`, `data_audit/independent_gate/audit.json`, `hitl/analysis/summary.json`, `user_study/study_status.json` và source report/verifier.

Khuyến nghị **đóng bằng chứng lõi**, thay vì huấn luyện thêm hoặc mở tính năng phụ. Huấn luyện lại chỉ xem xét nếu lỗi correctness buộc phải làm hoặc có yêu cầu mới; khi đó phải dự báo lại hạn và giữ holdout đúng cách. Báo cáo hiện có kết quả replay 402 ảnh nhưng không chứng minh Test độc lập; không lặp suy luận chỉ để thay timestamp.

### C01: Đối chiếu ba mốc trước với bằng chứng có thật

**Files**
- Create: `docs/evaluation/milestone_scope_matrix.csv`.
- Read only: `evaluation/selected_model.json`, `ai_training/splits/unified_vinmec_clean_2026-10-06/manifest.json`, `checkpoints/unified_vinmec_refine_2026-10-06/lr_3e-04/{run_config.json,baseline_training_history.json}`, `.superpowers/sdd/2026-10-16-system-evaluation-and-prototype/progress.md`.
- Verify: source artifact existence/hash, không viết test cho prose.

**Interfaces:** consumes hồ sơ nguồn; produces CSV `milestone,requirement,evidence_path,evidence_status,limitation,next_action`.

- [ ] 1. Liệt kê từng yêu cầu của các mốc 06/09–20/09, 21/09–05/10, 06/10–18/10 thành hàng riêng.
- [ ] 2. Đối chiếu path/hash/config/log của từng hàng; Patient ID chưa xác minh ghi UNKNOWN/BLOCKED, không tick theo lịch.
- [ ] 3. Kiểm tra model so sánh đã có chỉ dựa Validation; không tạo thêm experiment để lấp ô.
- [ ] 4. Xác nhận đủ luồng raw→preprocess→training→prediction→mask→metric bằng file hiện có hoặc ghi thiếu cụ thể.
- [ ] 5. Review CSV, ghi owner của evidence thiếu; commit riêng `docs: align milestone evidence with confirmed thesis scope`.

**Acceptance:** mỗi yêu cầu có artifact hoặc lý do thiếu; không backdate hoàn thành. **Effort:** 1h. **Dependency:** none.

### C02: Một policy nghiệm thu chung, bỏ default tạo bằng chứng giả

**Files**
- Modify: `scripts/build_evaluation_report.py:build_report,generate_final_checks,main,generate_markdown_report`, `scripts/verify_evaluation_release.ps1` phần final checks.
- Test: `tests/test_evaluation_report.py`, `tests/test_release_evidence.py`.

**Interfaces:** thêm `derive_release_status(checks:dict,independent_gate:dict,user_study:dict,hitl:dict)->dict` trong report builder; outputs `prototype_ready,evaluation_complete,clinician_validation,blockers,limitations`. Hai đường build_report/generate_final_checks và verifier dùng cùng kết quả Python, không tự tính completion riêng. Giữ `build_report` tham số hiện có, đổi default prototype_checks_passed=False; bổ sung `checks:dict|None=None` và evidence path CLI `--checks`.

- [ ] 1. Thêm test `test_fallback_is_not_a_clinician_blocker`: đủ gate khoa học/kỹ thuật + fallback có evidence → evaluation_complete=true, clinician_validation=false; independent BLOCKED vẫn false.
- [ ] 2. Thêm `test_unknown_evidence_has_no_defaults`, `test_browser_skip_prevents_readiness`, `test_status_build_paths_agree`: thiếu dữ liệu → timestamp tạo thực UTC, hash null/UNKNOWN, technical_count null hoặc 0 chỉ khi có cohort xác minh; không fallback hash checkpoint hoặc đếm một người tự động.
- [ ] 3. Chạy isolated pytest hai file, xác nhận RED do policy hiện tại. Sau đó implement policy: readiness cần command exit0, browser live PASS cùng revision/checkpoint, save/export evidence; evaluation còn cần independent run COMPLETE + quantitative/error/HITL outputs hợp lệ và study hoặc fallback evidence. Gate PASS một mình không đủ.
- [ ] 4. Cho CLI nhận actual check log, bỏ `prototype_checks_passed=True` cố định; dùng UTC lúc chạy, giữ run timestamps lịch sử đúng nguồn; “SHA-256” là mã băm toàn vẹn, không viết “mã hóa ZIP”.
- [ ] 5. Chạy lại hai file PASS, kiểm tra fallback/gate fixture matrix; commit `fix: align release gates with conditional clinician evaluation`.

**Acceptance:** cùng inputs tạo cùng trạng thái giữa các artifact; không bác sĩ không thành clinician_validation; không nới Test độc lập. **Effort:** 2–3h. **Dependency:** C01.

### C03: Phân loại provenance session và đếm người tham gia đúng

**Files**
- Modify: `evaluation/hitl_analysis.py:analyze_hitl,summarize_questionnaire,main`, `scripts/export_hitl_sessions.py:export_hitl_sessions`.
- Create: `docs/evaluation/hitl_session_provenance.csv` (chỉ schema/template và metadata khử định danh được phép).
- Test: `tests/test_hitl_analysis.py`, `tests/test_user_study_summary.py`.

**Interfaces:** `analyze_hitl` thêm optional `participant_registry:list[dict]|None=None`; registry rows `participant_code,role_verified,consent_status,source_evidence,data_origin,session_ids`. Session classification `verified_clinician|verified_technical|technical_fixture|unverified`; session count không phải participant count. CLI thêm `--participant-registry`.

- [ ] 1. Thêm `test_self_declared_clinician_is_not_verified_participant`, `test_missing_registry_quarantines_clinician_sessions`, `test_repeated_sessions_count_one_participant`, `test_missing_gt_preserves_null_delta`.
- [ ] 2. Chạy isolated pytest RED. Kiểm tra nguồn của 4 session gắn clinician trong tổng 32 session, chỉ đọc DB được phép ở chế độ readonly; không xuất danh tính/token ra terminal.
- [ ] 3. Giữ raw logs nguyên vẹn, bổ sung registry/disposition; fixture/demo loại khỏi user study; thiếu evidence gắn unverified, không tự đổi thành bác sĩ thật hoặc mặc định technical participant.
- [ ] 4. Sinh lại summary vào **thư mục run mới**, lưu input hashes và classification/exclusion counts; technical timing vẫn tách cohort; missing reference giữ ΔDice/ΔIoU null.
- [ ] 5. Chạy test PASS, so sánh số session/person với study_status và notes; commit `fix: separate verified participants from technical sessions`.

**Acceptance:** không suy có bác sĩ từ JWT hay role string; mâu thuẫn 4 session/0 người có disposition hoặc quarantine rõ. **Effort:** 1.5–2.5h + xác minh nguồn UNKNOWN. **Dependency:** C01; C02 report dùng output mới.

### C04: Full regression hiện hành thay vì bốn file được chọn

**Files**
- Modify: `scripts/verify_evaluation_release.ps1` phần pytest selection/output/server lifecycle; `tests/test_release_evidence.py`.
- Read: `tests/serve_isolated_app.py`, `docs/evaluation/release_runbook.md`.

**Interfaces:** verifier ghi `test_scope=full|selected`, `collected_count`, command list/hash/version; full release dùng `pytest.main(['tests','-q','--tb=short'])` sau isolated import bootstrap, không dùng bốn file list. Output directory mới qua tham số `-OutputDir` hiện có; không ghi đè report cũ.

- [ ] 1. Thêm `test_full_verifier_does_not_select_four_files` và `test_selected_suite_cannot_claim_full_regression` bằng source/config/subprocess fixture; kiểm tra missing/skipped test group không được coi đã chạy.
- [ ] 2. Chạy test RED; sửa selection và reporting. Chạy collection trong runtime riêng trước main import; giữ secret chỉ trong test environment, không đưa vào report shareable.
- [ ] 3. Chạy full isolated suite và Node/Playwright live vào thư mục mới. Retain exact failures; không bypass test nhãn/clinical để đạt PASS. Server helper phải xác nhận đúng PID/runtime/checkpoint, không dùng service khác đang chiếm port8027.
- [ ] 4. Mỗi failure có traceback/file/test/input; tạo corrective task nhỏ nếu có lỗi mới, chỉ sửa trong luồng lõi. Re-run affected tests rồi full regression sau fix.
- [ ] 5. Commit verifier/tests riêng `test: distinguish full regression from selected release checks`.

**Acceptance:** có log full collection + current execution result hoặc FAIL/BLOCKED rõ; không nói 30 passed là toàn bộ suite. **Effort:** 1–2h nếu xanh, lỗi phát hiện phải dự báo lại. **Dependency:** C02–C03 trước final run.

### C05: Giữ independent Test gate và chốt nhánh dữ liệu

**Files**
- Modify: `docs/evaluation/milestone_scope_matrix.csv`, `docs/evaluation/test_access_ledger.csv` chỉ bổ sung sự kiện có thật.
- Read: `evaluation/protocol.py`, `evaluation/run_evaluation.py`, `evaluation/milestone_3_final/data_audit/independent_gate/audit.json`.
- Conditional Create: cohort/lock/run mới theo CLI đã triển khai, tuyệt đối không sửa split cũ.

**Interfaces:** evidence source→protocol audit; output independent PASS + locked run hoặc BLOCKED + yêu cầu còn thiếu.

- [ ] 1. Đối chiếu Patient ID nguồn, nhãn/quyền sử dụng và lịch sử train/val/development; nguồn chưa có thì ghi missing rõ và owner.
- [ ] 2. Nếu đủ, preflight + freeze theo CLI thực tế `python -m evaluation.run_evaluation --help`; khóa model/threshold/preprocess trước suy luận trên cohort chưa dùng. Nếu không đủ, dừng nhánh này và ghi BLOCKED; không đổi tên 402 ảnh replay.
- [ ] 3. Tận dụng quantitative/error artifacts legacy đã có, giữ nhãn retrospective và native coordinate; không chạy tuning hoặc chọn subset điểm đẹp.
- [ ] 4. Khi thực sự có independent run: chạy metric oracle/regression, kiểm tra counts/hash/readback và per-case IDs; cập nhật access ledger đúng thời điểm.

**Acceptance:** mapping chưa xác minh thì evaluation_complete luôn false; thiếu bác sĩ không che lấp blocker Test. **Effort:** 0.5–1h triage + thời gian nguồn/compute UNKNOWN. **Dependency:** C01; song song việc nội bộ, không chặn demo.

### C06: Nghiệm thu manual/demo và đối chiếu artifact trước đóng mốc

**Files**
- Modify: `docs/evaluation/manual_acceptance.md`, `docs/evaluation/release_runbook.md`, `README.md`, `MODEL_CARD.md` phần phạm vi/chứng cứ.
- Create: `docs/evaluation/2026-10-18-core-acceptance.md` sau phiên thực tế; file ghi actual timestamp, không tự điền trước.
- Test: existing `tests/workspace_v2_release_e2e.js`, `tests/test_research_export.py` và launcher `-CheckOnly`.

**Interfaces:** confirmed scope + current check log→manual result + 5–7 phút demo script; không thêm API tính năng.

- [ ] 1. Đối chiếu hash trong manual protocol với checkpoint thực; hash `417828fa74340...` đang khác manifest, cần sửa tài liệu theo hash đọc lại, giữ audit note lỗi phiên bản. Checkbox từng bước chỉ tick khi thực sự quan sát.
- [ ] 2. Rehearse live Upload→AI→Original/Mask/Overlay→Edit/Undo→Confirm→Reload→Export. Kiểm tra bitwise mask và provenance; clinical sign/LLM/dashboard không nằm demo cốt lõi.
- [ ] 3. Thử offline save, đổi ảnh/ca, restart cùng DB, export đúng review; ghi máy/browser/version/thời gian actual. Ngưỡng latency1500ms trong mẫu manual hiện chưa có cơ sở nghiệm thu thầy xác nhận: ghi đo thực tế trên máy và đánh giá trải nghiệm, không coi vượt ngưỡng tự đặt là thất bại khoa học.
- [ ] 4. Review report mới từ C02–C05: mỗi PASS có log, clinician status tách riêng, no-GT delta null, independent BLOCKED nếu chưa đủ; commit docs riêng sau kiểm tra.

**Acceptance:** core demo trên máy đích có bằng chứng; bản manual không phải biểu mẫu được tick sẵn; không tuyên bố dùng điều trị. **Effort:** 1–2h. **Dependency:** C04; C05 status rõ, không nhất thiết PASS để demo có giới hạn.

### C07: Báo cáo KLTN và bảo vệ từ 19/10

**Files**
- Create: `docs/evaluation/thesis_handoff.md`.
- Modify: `docs/evaluation/milestone_scope_matrix.csv` và report mới qua `scripts/build_evaluation_report.py`, không viết số metric bằng tay vào generator.
- Verify: evidence cross-check, không viết unit test cho chương văn bản.

**Interfaces:** artifacts đã audit→bảng/hình/chương kết quả/hạn chế, checklist bảo vệ và backlog còn lại.

- [ ] 1. Ngày19/10 chốt baseline version/hash và bảng nội dung: bài toán/phạm vi; dữ liệu; pipeline; U-Net; HITL prototype; thực nghiệm; hạn chế; kết luận.
- [ ] 2. Ngày20/10 đối chiếu tất cả bảng/hình với CSV/summary/model hash; phân biệt Validation, retrospective Test và independent Test; không có independent thì nói chưa đạt yêu cầu này.
- [ ] 3. Ngày21/10 trở đi chuẩn bị slide/demo/Q&A theo lịch bảo vệ thực tế UNKNOWN; giải thích leakage, nhãn, mask editing, metric empty cases và giới hạn user study. Không tự đặt ngày bảo vệ.
- [ ] 4. Chỉ sửa lỗi correctness có failing test sau đóng baseline; bổ sung cohort/clinician thật bằng run mới có version. LLM/VLM/sinh báo cáo/dashboard giữ backlog tới khi core gate PASS và người dùng chọn mở scope.
- [ ] 5. Self-review report: không đồng nhất abnormal/malignant, pixel recall/clinical sensitivity, session/person, hash/encryption hoặc code task complete/scientific objective complete.

**Acceptance:** mỗi nhận định có evidence; backlog có owner và điều kiện mở; báo cáo/bảo vệ bám tên đề tài chính xác. **Effort:** 1–2h handoff; thời gian viết toàn KLTN cần lập theo khối lượng bản thảo thật. **Dependency:** C06 + C05 status.

## Timeline cập nhật và critical path

Ngày17/10: buổi đầu C01/C05 (1.5–2h), sau đó C02 (2–3h); C03 (1.5–2.5h) khi đã có registry evidence. Nếu thiếu nguồn, quarantine và hoàn thành nhánh kỹ thuật, không chờ vô hạn. Không coi 16/10 là ngày làm việc còn lại.

Ngày18/10: buổi đầu C04 (1–2h nếu suite xanh), buổi sau C06 (1–2h) và chốt handoff C07 (1h). Bác sĩ chỉ tổ chức nếu đã tiếp cận, quyền dữ liệu và prototype phù hợp; không chờ bác sĩ để hoàn thành hồ sơ fallback. Thời gian sửa lỗi mới/full-suite UNKNOWN; nếu không đủ thì bàn giao có danh sách FAIL/BLOCKED, không ép chữ COMPLETE.

Tổng nội bộ 8.5–14h cộng lỗi phát hiện/external wait. Critical path: C01→C02/C03→C04→C06→C07. Independent scientific path C05 phụ thuộc nguồn và không có hạn đảm bảo. Từ19/10 tập trung KLTN; không lùi việc viết chỉ để mở tính năng phụ.

## Definition of Done và deliverables

- [ ] Tên đề tài/phạm vi và cả bốn mốc có matrix evidence.
- [ ] Core flow chạy live, persisted mask/export đúng version; manual demo thực sự được thực hiện.
- [ ] Full-suite result có log hiện hành, không thay bằng selected30 tests.
- [ ] Quantitative/error/HITL analysis cùng model/config, nguồn session nhất quán.
- [ ] Independent Test có source evidence và run hợp lệ hoặc ghi BLOCKED; BLOCKED không đạt full scientific DoD.
- [ ] Clinician thật hoặc fallback đã nghiệm thu; clinician_validation không bị tự nâng.
- [ ] Report/final checks cùng policy, không timestamp/hash/count cố định giả bằng chứng.
- [ ] Handoff từ19/10 đủ bảng/hình/code/run commands và hạn chế; LLM/VLM/dashboard ở backlog có điều kiện.

## Self-review và handoff

Đã kiểm tra: bao phủ hướng thầy xác nhận và các mốc; không lặp 20 task đã triển khai; 7 task mới có files/interfaces/actions/acceptance/dependency; các sai khác được trace tới source cụ thể; không có yêu cầu nâng model/tuning bằng Test. C05 là blocker nguồn thật, C03 có thể quarantine; không giả data để mở gate. Nice-to-have không nằm critical path. Kiểm tra tài liệu không chứng minh runtime PASS; lượt này chỉ đọc source/artifact, không chạy lại evaluation hoặc thu thập người tham gia.

Trước thực thi, người dùng review spec/plan cập nhật và chọn/preserve execution method. Không suy từ ledger SDD là người dùng vừa chọn phương thức cho công việc mới. Khuyến nghị native cho đợt closure nhỏ do các thay đổi chủ yếu ở report/verifier dùng chung interface; không spawn agent trong lượt lập tài liệu.
