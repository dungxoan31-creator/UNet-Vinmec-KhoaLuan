# Gate 6 — Clinical UX and Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development after execution authorization. UI work must follow approved invariants; no redesign is performed during planning.

**Goal:** Đóng AUD-021–029 bằng report hierarchy, form dữ liệu cần thiết, consistent shortcuts, keyboard và recovery đúng bệnh nhân.

**Architecture:** Giữ DOM/component patterns hiện có; renderer dùng server/snapshot data model, không tạo clinical facts từ UI.

**Tech Stack:** Vanilla JS/CSS, Node tests, Playwright đã cài, PDF renderer hiện có.

**Spec:** [Approved design §10](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa [master](2026-11-05-full-spectrum-remediation-plan.md), G2 episode identity, G4 report/revision và G5 chart DTO. Không bỏ warning bắt buộc để giảm chữ. Không image generation/redesign branding, không thêm frontend framework/dependency.

## Review Focus

Kết luận dài/nhiều ảnh, năm sinh không bằng tuổi chính xác, input focus khi bấm C, 200% browser zoom và network ACK mơ hồ giữa hai ca. T23–T26 kiểm tra từng nhóm.

## T23 — Phiếu ưu tiên kết quả, định danh đọc được và export honest

**Files:** Modify `frontend/app/report-preview.js`, `frontend/css/report-preview.css`, `backend/services/report_generator.py`, `report_artifact.py`; Extend `tests/test_fe_02_report_preview.mjs`; Create `tests/report_layout_e2e.cjs`, `tests/test_report_layout_contract.py`.

**Interfaces:** `renderReportDocument(studyOrSnapshot,assets)` giữ entry hiện có nhưng display-model từ T20; `exportAvailability(capabilities,policyStatus) -> {enabled,reason}` dùng cả viewer/report; `representative_image_id` chỉ từ clinician selection trong revision, không tự chọn ảnh mang kết luận.

- [ ] **RED:** `test_first_page_prioritizes_clinician_conclusion_and_laterality`, `test_long_pseudonym_prints_all_characters`, `test_many_images_continue_to_appendix_without_clipping`, `test_blocked_export_not_presented_as_download`.
  ```javascript
  assert.ok(firstPageText.includes('Kết luận của bác sĩ'));
  assert.equal(exportButton.disabled, true);
  assert.ok(extractedPdfText.includes(fullSyntheticPseudonym));
  ```
- [ ] **Verify RED:** N/P targets và B report layout; test snapshot có câu kết luận dài, null conclusion, ảnh L/R và 20 images; không yêu cầu luôn đúng 2 trang.
- [ ] **Implement:** summary: identity/status từng bên/clinician conclusion/O-RADS/morphology, ảnh đại diện chỉ nếu chọn; appendix provenance/toàn bộ evidence, wrap ID theo nhóm không cắt ký tự. Disabled export có lý do nhìn thấy và accessible description; không gán onclick toast giả tải.
- [ ] **GREEN:** N/P và B A4 prepared print/PDF at 1920×1080,1440×900,1366×768; text extraction hash/ảnh đối chiếu T20. Native print dialog chưa test phải ghi riêng.
- [ ] **Checkpoint:** ký số vs attestation/RUO distinction giữ nguyên trên preview/reprint, không lấy case mutable thay artifact finalized.

## T24 — Trường tối thiểu và gợi ý tuổi có nguồn

**Files:** Modify `frontend/app/intake.js`, `form-validator.js`, `adnex.js`, `backend/services/episode_identity.py`, `backend/schemas/schemas.py`; Create `tests/test_age_provenance.mjs`, `tests/test_episode_age_precision.py`; Extend `tests/test_form_validator.mjs`.

**Interfaces:** `ageSuggestion(episodeIdentity,studyDate) -> {value:number|null,precision:'YEAR_ESTIMATE'|'EXACT'|'UNKNOWN',source:string,confirmed:false}`; server snapshot giữ `age_years`, `age_precision`, `age_confirmed_by`, `age_confirmed_at`. Born-year only không tự biến thành exact; research anonymous vẫn nhập tuổi phục vụ clinical calculation khi thích hợp mà không tạo PID.

- [ ] **RED:** `test_birth_year_prefill_is_unconfirmed_estimate`, `test_unknown_year_never_defaults_to_zero`, `test_historical_age_uses_exam_date_not_current_clock`, `test_phone_and_hometown_not_required_or_persisted`.
  ```javascript
  assert.deepEqual(ageSuggestion({birth_year:1990}, '2020-06-01'), {value:30,precision:'YEAR_ESTIMATE',source:'episode.birth_year',confirmed:false});
  assert.equal(adnexRequestBeforeAgeConfirmation, null);
  ```
- [ ] **Verify RED:** N/P targets; test tên đầy đủ fields đã bỏ required đồng thời không lén lưu PII không còn dùng.
- [ ] **Implement:** lấy gợi ý từ episode snapshot T06, user confirm tuổi lúc khám trước ADNEX; thay ngày/identity invalidates confirmation. Form chỉ yêu cầu dữ liệu có mục đích; national ID/phone/hometown không thu thập trong pipeline nếu chưa có approved consumer.
- [ ] **GREEN:** N/P/PG contract và B intake→viewer→ADNEX prefill→confirm→reopen; reject mismatch age/confirmation source trên server, no overwriting manually confirmed value bằng async metadata.
- [ ] **Checkpoint:** không coi birth_year hay name là identity linkage, không infer menopause từ tuổi; giữ model descriptor missing nếu chưa xác nhận.

## T25 — Shortcut, tour và drilldown keyboard cùng nguồn

**Files:** Modify `frontend/app/viewer-shortcuts.js`, `viewer.js`, `personal.js`, `onboarding.js`, `admin-reports.js`; Extend `tests/test_viewer_shortcuts.mjs`, `test_admin_analytics_ui.mjs`; Create `tests/keyboard_workflow_e2e.cjs`.

**Interfaces:** `VIEWER_SHORTCUTS` export map {key,action,label,description}; chọn C=caliper D1/D2 như toolbar hiện có, Shift+C=compare, loại nhánh unreachable `else if k==='c'`. `getViewerShortcut(event)->string|null` bỏ input/textarea/select/contenteditable/composition/modifier không phù hợp; chart dùng button native và aria-pressed/aria-label.

- [ ] **RED:** `test_c_handler_help_and_tooltip_use_same_action`, `test_typing_c_in_notes_does_not_start_caliper`, `test_shift_c_compares_without_mutating_mask`, `test_orads_filter_supports_tab_enter_space`, `test_tour_describes_unilateral_and_explicit_run`.
  ```javascript
  assert.equal(getViewerShortcut({key:'c',target:notesInput}), null);
  assert.equal(getViewerShortcut({key:'C',shiftKey:true,target:canvas}), 'compare');
  ```
- [ ] **Verify RED:** N targets + B keyboard; event fixtures gồm ctrl/meta/alt/isComposing đúng signature, không bỏ browser default typing.
- [ ] **Implement:** một shortcut registry cho handler/tooltips/help; accessible native controls, focus/selected state khi filter async; tour dùng capability/status xác thực, một bên không hướng dẫn thêm ảnh sai bên để đủ cặp.
- [ ] **GREEN:** N/B và reviewer manual keyboard pass trên synthetic cases; focus-visible, Escape/Tab modal, Ctrl+S không triggered khi quyền/lease sai; document screen-reader/physical keyboard scope thật.
- [ ] **Checkpoint:** alias legacy không được hai action cùng key; không thay semantics clinical fields để phím tắt thuận tiện.

## T26 — Responsive, draft/recovery và hai ca liên tiếp

**Files:** Modify `frontend/css/workspace.css`, `frontend/css/workstation-premium.css`, `frontend/app/viewer.js`, `frontend/app/state.js`, `frontend/app/review.js`, `frontend/app/leases.js`, `frontend/app/navigation.js`, `backend/app/routers/reviews.py`; Create `tests/test_draft_revision_scope.mjs`, `tests/clinical_recovery_responsive_e2e.cjs`; Extend `tests/workstation_viewer_e2e.js`.

**Interfaces:** `draftKey({userId,facilityId,studyId,imageId,clinicalRevisionId,reviewRevision}) -> string`; `classifyDraftConflict(localDraft,serverSnapshot)->'MATCH'|'STALE'|'WRONG_CONTEXT'`; `recoverReviewAcknowledgement(requestId) -> Promise<dict>` gọi endpoint read ACK theo authorized scope (thêm GET `/api/cases/{study_id}/review-requests/{request_id}` trong reviews router, không auto replay payload đổi).

- [ ] **RED:** `test_patient_switch_never_restores_previous_draft`, `test_timeout_after_commit_reuses_ack_not_duplicate_review`, `test_stale_draft_requires_explicit_resolution`, `test_toolbar_and_panel_remain_reachable_at_zoom_and_narrow_width`, `test_cancelled_touch_drag_does_not_keep_drawing`.
  ```javascript
  assert.notEqual(draftKey(caseAContext), draftKey(caseBContext));
  assert.equal(classifyDraftConflict(draftRevision1, serverRevision2), 'STALE');
  assert.equal(secondCaseNotes, '');
  ```
- [ ] **Verify RED:** N/B targets; network injection phân biệt response lost-after-server-commit và failure-before-commit, không chỉ abort cả request.
- [ ] **Implement:** preserve unsaved data đúng context, no blind online replay; explicit compare stale content; toolbar/panel layout ưu tiên ảnh/action, không hide controls T14. Pointer cancel/lostcapture/blur clear drag state; reduced motion không phá useful feedback.
- [ ] **GREEN:** B ở 1920×1080,1440×900,1366×768,1024×768,390×844; browser zoom thực 125%/200% nếu engine support, CSS zoom ghi chỉ stress sample. Synthetic touch và keyboard thử thực, không suy gesture pass từ viewport. Failed-save status/draft + reopen ACK đúng revision.
- [ ] **Checkpoint G6:** ghi số thao tác/thời gian từ flow thực khi đo, không biến automation ms thành thời gian bác sĩ. Physical touch/mic/screen reader chưa có vẫn NOT TESTED.
