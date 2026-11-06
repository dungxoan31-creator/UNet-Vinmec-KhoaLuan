# Gate 7 — Model Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans or superpowers:subagent-driven-development after execution authorization. Model training/replacement is not authorized by this plan.

**Goal:** Xử lý AUD-030 trung thực; ràng buộc model/provenance/ruleset với research và clinical release gates.

**Architecture:** Không sửa lineage cho hợp thức hóa. Artifact lệch scope vẫn research candidate; release kiểm tra exact approved model/ruleset/version/evidence.

**Tech Stack:** Existing model registry/inference, JSON/SHA-256, pytest; không huấn luyện hay tải weights mới.

**Spec:** [Approved design §11](../specs/2026-11-05-full-spectrum-remediation-design.md).

## Global Constraints

Kế thừa [master](2026-11-05-full-spectrum-remediation-plan.md). Giữ SHA-256 image-level dedup, letterbox 512×512, HITL và core Dice+BCE. Không sửa actual loss metadata thành ComboLoss nếu checkpoint không tương ứng. Patient-level independence chưa được chứng minh.

## Review Focus

Hash hợp lệ nhưng loss lệch scope, model fallback không rõ, preprocessing drift, validation-tuned metric bị gọi independent và O-RADS rule chưa xác minh. T27/T28 có tests, external reference chưa verified không được đóng bằng text.

## T27 — Provenance eligibility và cảnh báo deviation

**Files:** Modify `backend/services/model_service.py`, `backend/app/config.py`, `backend/app/routers/health.py`, `frontend/app/admin-models.js`; Create `backend/services/model_governance.py`, `tests/test_model_governance_contract.py`, `docs/evaluation/full-spectrum-model-deviations.md`; Read-only `evaluation/selected_model.json` và weights.

**Interfaces:** `assess_model_scope(manifest: dict, *, required_loss: str='DICE_BCE', expected_input_size: tuple=(512,512)) -> dict` trả `scope_status,blockers,model_identity`; `model_identity` gồm checkpoint_sha256,preprocessing_version,threshold,architecture; source manifest không bị ghi lại. Research inference có thể tiếp tục với warning đúng, clinical eligibility blocked khi deviation/evidence thiếu.

- [ ] **RED:** `test_hash_valid_advanced_loss_is_not_combo_compliant`, `test_manifest_input_geometry_mismatch_blocks_use`, `test_missing_provenance_cannot_be_requested_as_fallback`, `test_model_identity_change_invalidates_policy_scope`.
  ```python
  decision = assess_model_scope({**manifest_fixture,"loss_function":"AdvancedHybridLoss(0.5 FocalTversky + 0.3 SoftDice + 0.2 BCE)"})
  assert decision["scope_status"] == "DEVIATION_RESEARCH_ONLY"
  assert decision["blockers"]
  ```
- [ ] **Verify RED:** `P tests/test_model_governance_contract.py`; fixtures copy JSON in memory, no checkpoint/manifest edits.
- [ ] **Implement:** governance report và UI exact truthful lineage, no silent unloaded model fallback; clinical policy T16 compares full model identity, not chỉ model_version text. Checkpoint hash/preprocess provenance giữ nguyên trên prediction.
- [ ] **GREEN:** P/PG scope interactions + registry fail-closed/provenance/image-classifier tests already safe; before/after weights/manifest checksum unchanged. Không chạy training benchmarks/data prep để tạo candidate mới.
- [ ] **Checkpoint AUD-030:** có deviation ledger và guard đúng chưa đồng nghĩa có compliant model. Artifact ComboLoss chưa có evidence thì trạng thái `BLOCKED_EXTERNAL_ARTIFACT`, không đánh dấu toàn bộ phương pháp luận đã phù hợp.

## T28 — Validation claims và clinical ruleset evidence

**Files:** Modify `backend/services/cdss_engine.py` metadata/guard only, `backend/services/release_policy.py`, `backend/app/routers/health.py`, `frontend/app/image-classification.js`; Extend `tests/test_release_evidence.py`, `test_cdss_fail_closed.py`; Create `tests/test_clinical_evidence_boundary.py` và `docs/clinical_validation/full-spectrum-release-evidence-checklist.md`.

**Interfaces:** `validate_model_evidence(evidence: dict, model_identity: dict) -> list[str]` và `validate_ruleset_evidence(evidence: dict, ruleset_version: str) -> list[str]` trong model_governance.py. Các hàm chỉ kiểm contract/evidence version, không tự xác nhận đúng chuẩn y khoa từ URL hoặc boolean user gửi.

- [ ] **RED:** `test_validation_tuned_metrics_never_satisfy_independent_clinical_gate`, `test_unverified_patient_identity_remains_blocked`, `test_unknown_ruleset_reference_never_infers_safe_orads`, `test_class_score_label_not_disease_probability`.
  ```python
  assert "PATIENT_INDEPENDENCE_UNVERIFIED" in validate_model_evidence(evidence_fixture, model_identity)
  assert policy_decision["allowed"] is False
  ```
- [ ] **Verify RED:** P targets + `N tests/test_image_classification_ui.mjs`; do not query clinical datasets hoặc rewrite risk rules chỉ để đạt expected category.
- [ ] **Implement:** evidence checklist dataset/label/split/protocol/cohort/clinical review, scope/version match; unsupported CDSS remains unsupported. Boundary 30mm giữa core text/rule cần verified reference reconciliation trước bất kỳ đổi logic, không tự chọn ngưỡng y khoa mới.
- [ ] **GREEN:** P fail-closed + synthetic rule matrix hiện có chỉ chứng minh tính tất định; báo riêng validation/calibration/clinical study còn blocked. External source review do người có chuyên môn và cơ sở chấp nhận, không invented DOI/license/metrics.
- [ ] **Checkpoint G7:** không đổi loss, weights, train split hoặc clinical readiness chỉ để đóng finding; bàn giao danh sách input còn thiếu rõ ràng.
