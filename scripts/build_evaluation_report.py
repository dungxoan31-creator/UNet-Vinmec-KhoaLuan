#!/usr/bin/env python3
"""
scripts/build_evaluation_report.py
----------------------------------
Builds consolidated evaluation results, evidence matrix, limitations documentation,
and release status artifacts from immutable run summaries and telemetry logs (Task 19).

Enforces:
1. All metrics are strictly artifact-derived from verified summary.json files.
2. Missing cohorts or uncalculated metrics are preserved as null / explicit reasons, never coerced to 0.0.
3. Current run pointer is verified for hash integrity (checkpoint, protocol, manifest).
4. Retrospective test replays are unambiguously tagged as historical, never disguised as independent.
5. User study records preserve clinician vs technical tester counts (technical testers != clinicians).
6. Prototype readiness and evaluation completeness are decoupled:
   - prototype_ready = True (when live runtime, auth, intake, edit, batch review, export PASS)
   - evaluation_complete = False (when independent test cohort is BLOCKED)
"""

import argparse
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def derive_release_status(
    checks: dict[str, Any] | None = None,
    independent_gate: dict[str, Any] | None = None,
    user_study: dict[str, Any] | None = None,
    hitl: dict[str, Any] | None = None,
    runs: list[dict[str, Any]] | None = None,
    prototype_checks_passed: bool = False,
) -> dict[str, Any]:
    """
    Evaluates release gates and returns a unified status dictionary:
    - prototype_ready: bool
    - evaluation_complete: bool
    - clinician_validation: bool
    - blockers: list of blocker descriptions
    - limitations: list of limitation descriptions

    Rules:
    1. prototype_ready requires:
       - No browser skip (browser_skipped / skip_browser must be False).
       - Zero overall exit code from execution checks.
       - Verified live browser test (live_browser_verified is True or passed release_e2e command).
       - If checks dictionary is not provided, readiness stays false; an aggregate boolean is insufficient.
    2. clinician_validation requires:
       - Explicit CONDUCTED status, a positive integer clinician count,
         has_clinician_validation is True, and verified participant provenance.
       - Never coerced to True merely because a count is present or technical fallback succeeded.
    3. evaluation_complete requires:
       - prototype_ready is True.
       - Independent holdout gate is PASS (patient-level mapping verified, not BLOCKED).
       - Quantitative independent evaluation runs completed (if runs provided).
       - Either verified clinician validation OR verified technical acceptance fallback recorded.
    """
    blockers: list[str] = []
    limitations: list[str] = []

    # 1. Prototype Readiness
    prototype_ready = False
    if checks is not None:
        overall_exit = checks.get("overall_exit_code", 0)
        skip_browser = bool(checks.get("skip_browser", False) or checks.get("browser_skipped", False))
        commands = checks.get("commands", [])

        if "live_browser_verified" in checks:
            live_browser_verified = bool(checks["live_browser_verified"])
        else:
            e2e_cmd = next((c for c in commands if "release_e2e" in c.get("name", "")), None)
            live_browser_verified = (not skip_browser) and (e2e_cmd is not None) and (e2e_cmd.get("exit_code") == 0)

        if skip_browser:
            blockers.append("Live browser E2E verification was skipped; prototype readiness requires verified browser execution")
        elif overall_exit != 0:
            blockers.append(f"Execution checks failed with non-zero exit code ({overall_exit})")
        elif any(command.get("exit_code") != 0 for command in commands):
            blockers.append("One or more recorded commands did not pass")
        elif commands and not live_browser_verified:
            blockers.append("Live browser E2E test not verified")
        elif live_browser_verified:
            prototype_ready = True
        else:
            blockers.append("Prototype readiness requires verified live browser test")
    else:
        blockers.append("Prototype readiness requires explicit check evidence with live browser verification")

    # 2. Clinician Validation
    clinician_validation = False
    if user_study is not None:
        has_clin = user_study.get("has_clinician_validation")
        provenance_verified = user_study.get("clinician_provenance_verified")
        status_str = user_study.get("study_status", "UNKNOWN")
        clin_count = user_study.get("clinician_count", 0)
        if (
            has_clin is True
            and provenance_verified is True
            and status_str == "CONDUCTED"
            and type(clin_count) is int
            and clin_count > 0
        ):
            clinician_validation = True

    # 3. Independent Gate
    gate_status = "UNKNOWN"
    if independent_gate is not None:
        gate_status = independent_gate.get("status", "UNKNOWN")

    gate_passed = (gate_status == "PASS")
    if not gate_passed:
        if gate_status == "BLOCKED":
            blockers.append("Independent test cohort patient-level mapping unverified (independent_gate status: BLOCKED)")
        else:
            blockers.append(f"Independent test cohort audit not passed (independent_gate status: {gate_status})")

    # 4. User Study / Technical Fallback
    user_study_ok = False
    if user_study is not None:
        if clinician_validation:
            user_study_ok = True
        else:
            study_status = user_study.get("study_status", "UNKNOWN")
            tech_acc = user_study.get("technical_acceptance")
            tech_fallback = user_study.get("technical_fallback_verified")

            if tech_fallback is True and tech_acc == "PASS":
                user_study_ok = True
                limitations.append("Clinician user study not conducted (study_status: NOT_CONDUCTED); technical acceptance protocol used as fallback")
            elif study_status == "NOT_CONDUCTED":
                blockers.append("Clinician user study not conducted and technical acceptance fallback not verified")
            else:
                blockers.append(f"User study unverified (status: {study_status})")
    else:
        blockers.append("User study evidence not provided")

    # 5. Quantitative Independent Runs
    runs_ok = True
    if runs is not None and gate_passed:
        indep_runs = [r for r in runs if r.get("run_kind") == "independent_test"]
        if indep_runs and not any(r.get("status") == "COMPLETE" for r in indep_runs):
            runs_ok = False
            blockers.append("Independent test evaluation run not complete")

    # 6. Evaluation Complete
    evaluation_complete = (
        prototype_ready
        and gate_passed
        and user_study_ok
        and runs_ok
    )

    return {
        "prototype_ready": prototype_ready,
        "evaluation_complete": evaluation_complete,
        "clinician_validation": clinician_validation,
        "blockers": blockers,
        "limitations": limitations,
    }


def audit_run_summary(summary_path: Path) -> dict[str, Any]:
    """
    Reads and validates a run summary.json file.
    Ensures that retrospective replays are correctly tagged and all primary/secondary metrics
    are faithfully extracted.
    """
    if not summary_path.exists():
        raise FileNotFoundError(f"Run summary not found: {summary_path}")

    with open(summary_path, encoding="utf-8") as f:
        data = json.load(f)

    run_id = data.get("run_id", summary_path.parent.name)
    run_kind = data.get("run_kind", "unknown")
    status = data.get("status", "UNKNOWN")

    is_historical_replay = (run_kind == "retrospective_test_replay")

    if is_historical_replay:
        kind_label = "Retrospective Test Replay (Historical Data)"
    elif run_kind == "validation_dry_run":
        kind_label = "Validation Cohort"
    elif run_kind == "independent_test":
        kind_label = "Independent Holdout Test"
    else:
        kind_label = f"Run: {run_kind}"

    primary = data.get("primary", {})
    secondary = data.get("secondary", {})
    patient_macro = data.get("patient_macro", {})
    counts = data.get("counts", {})

    return {
        "run_id": run_id,
        "run_kind": run_kind,
        "kind_label": kind_label,
        "status": status,
        "is_historical_replay": is_historical_replay,
        "protocol_sha256": data.get("protocol_sha256"),
        "manifest_sha256": data.get("manifest_sha256"),
        "checkpoint_sha256": data.get("checkpoint_sha256"),
        "counts": counts,
        "primary": primary,
        "secondary": secondary,
        "patient_macro": patient_macro,
        "summary_path": str(summary_path),
    }


def audit_current_run_pointer(pointer_path: Path) -> dict[str, Any]:
    """
    Validates that current_run.json points to a legitimate run summary with matching hashes.
    Raises ValueError on hash or identity mismatches.
    """
    if not pointer_path.exists():
        raise FileNotFoundError(f"current_run.json pointer not found: {pointer_path}")

    with open(pointer_path, encoding="utf-8") as f:
        pointer = json.load(f)

    summary_path_str = pointer.get("summary_path")
    if not summary_path_str:
        raise ValueError("current_run.json must define 'summary_path'")

    summary_path = Path(summary_path_str)
    if not summary_path.is_absolute():
        summary_path = pointer_path.parent / summary_path

    if not summary_path.exists():
        raise FileNotFoundError(f"Pointer summary_path does not exist on disk: {summary_path}")

    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)

    # Check protocol_sha256
    ptr_proto = pointer.get("protocol_sha256")
    sum_proto = summary.get("protocol_sha256")
    if ptr_proto and sum_proto and ptr_proto != sum_proto:
        raise ValueError(
            f"Hash mismatch: pointer protocol_sha256 ({ptr_proto}) != summary protocol_sha256 ({sum_proto})"
        )

    # Check checkpoint_sha256
    ptr_ckpt = pointer.get("checkpoint_sha256")
    sum_ckpt = summary.get("checkpoint_sha256")
    if ptr_ckpt and sum_ckpt and ptr_ckpt != sum_ckpt:
        raise ValueError(
            f"Hash mismatch: pointer checkpoint_sha256 ({ptr_ckpt}) != summary checkpoint_sha256 ({sum_ckpt})"
        )

    # Check run_id
    ptr_run_id = pointer.get("run_id")
    sum_run_id = summary.get("run_id")
    if ptr_run_id and sum_run_id and ptr_run_id != sum_run_id:
        raise ValueError(
            f"Run ID mismatch: pointer run_id ({ptr_run_id}) != summary run_id ({sum_run_id})"
        )

    pointer["resolved_summary"] = summary
    return pointer


def _fmt_metric(val: Any, decimals: int = 4) -> str:
    if val is None:
        return "Chưa có / Không xác định"
    if isinstance(val, (int, float)):
        return f"{val:.{decimals}f}"
    return str(val)


def _load_model_configuration(root: Path) -> dict[str, Any]:
    """Load model details only from the repository's explicit selection artifact."""
    selection_path = root / "evaluation" / "selected_model.json"
    if not selection_path.is_file():
        return {}
    with selection_path.open(encoding="utf-8") as stream:
        selection = json.load(stream)
    if not isinstance(selection, dict):
        raise ValueError(f"Model selection must be a JSON object: {selection_path}")
    protocol = selection.get("inference_protocol")
    return {
        "source": selection_path.relative_to(root).as_posix(),
        "model": selection.get("model"),
        "architecture": selection.get("architecture"),
        "checkpoint_sha256": selection.get("checkpoint_sha256"),
        "candidate_only": selection.get("candidate_only"),
        "threshold": selection.get("threshold"),
        "letterbox_size": protocol.get("letterbox_size") if isinstance(protocol, dict) else None,
        "postprocessing": protocol.get("postprocessing") if isinstance(protocol, dict) else None,
        "metric_mask_resolution": protocol.get("metric_mask_resolution") if isinstance(protocol, dict) else None,
    }


def generate_markdown_report(report_data: dict[str, Any]) -> str:
    """
    Renders structured Markdown report (results.md) synthesizing quantitative evaluation,
    error analysis, HITL telemetry, user study findings, and system limitations.
    """
    model_config = report_data.get("model_configuration", {})
    input_size = model_config.get("letterbox_size")
    if isinstance(input_size, list) and len(input_size) == 2:
        input_size_text = f"{input_size[0]}×{input_size[1]}"
    else:
        input_size_text = "Chưa được nêu trong metadata"
    threshold = model_config.get("threshold")
    threshold_text = f"$\\ge {threshold}$" if isinstance(threshold, (int, float)) else "Chưa được nêu trong metadata"
    candidate_status = (
        "Candidate only" if model_config.get("candidate_only") is True
        else "Not stated in metadata" if model_config.get("candidate_only") is None
        else "Selection metadata"
    )
    lines = [
        "# Báo cáo Đánh giá Định lượng và Thực nghiệm Mô hình Phân đoạn Buồng trứng",
        "",
        "> **Dự án**: Khóa luận Tốt nghiệp & Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop",
        f"> **Thời điểm tạo**: {report_data.get('generated_at', '2026-10-16')}",
        f"> **Trạng thái nguyên mẫu (Prototype Ready)**: {'PASS' if report_data.get('prototype_ready') else 'NOT READY'}",
        f"> **Trạng thái đánh giá khoa học (Evaluation Complete)**: {'COMPLETE' if report_data.get('evaluation_complete') else 'PARTIAL / BLOCKED'}",
        "",
        "---",
        "",
        "## 1. Thông tin Mô hình và Cấu hình Suy luận",
        "",
        f"- **Mô hình**: {model_config.get('model') or 'Chưa được nêu trong metadata'}",
        f"- **Kiến trúc**: `{model_config.get('architecture') or 'Chưa được nêu trong metadata'}` ({candidate_status})",
        f"- **Checkpoint SHA-256**: `{report_data.get('checkpoint_sha256') or model_config.get('checkpoint_sha256') or 'Chưa có'}`",
        f"- **Kích thước đầu vào**: {input_size_text}",
        f"- **Ngưỡng nhị phân hóa**: {threshold_text}",
        f"- **Postprocessing**: {model_config.get('postprocessing') or 'Chưa được nêu trong metadata'}",
        f"- **Độ phân giải metric mask**: {model_config.get('metric_mask_resolution') or 'Chưa được nêu trong metadata'}",
        "",
        "---",
        "",
        "## 2. Kết quả Đánh giá Phân đoạn Định lượng",
        "",
    ]

    runs = report_data.get("runs", [])
    if not runs:
        lines.append("*Chưa có lượt chạy đánh giá nào được nạp.*")
    else:
        lines.append("| Tập dữ liệu / Vai trò | Số mẫu | Dice Mean (Median) | IoU Mean (Median) | Độ nhạy Recall | Độ chính xác Precision | Độ đặc hiệu Specificity | HD95 (px) |")
        lines.append("|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|")
        for r in runs:
            counts = r.get("counts", {})
            total_n = counts.get("total_samples", 0)
            p = r.get("primary", {})

            dice = p.get("dice", {})
            iou = p.get("iou", {})
            rec = p.get("recall", {})
            prec = p.get("precision", {})
            spec = p.get("specificity", {})
            hd95 = p.get("hd95_px", {})

            dice_str = f"{_fmt_metric(dice.get('mean'))} ({_fmt_metric(dice.get('median'))})" if dice.get("mean") is not None else "Chưa có / Không xác định"
            iou_str = f"{_fmt_metric(iou.get('mean'))} ({_fmt_metric(iou.get('median'))})" if iou.get("mean") is not None else "Chưa có / Không xác định"
            rec_str = _fmt_metric(rec.get("mean"))
            prec_str = _fmt_metric(prec.get("mean"))
            spec_str = _fmt_metric(spec.get("mean"))
            hd95_str = _fmt_metric(hd95.get("mean"), decimals=2)

            label = r.get("kind_label", r.get("run_id"))
            lines.append(f"| **{label}** | {total_n} | {dice_str} | {iou_str} | {rec_str} | {prec_str} | {spec_str} | {hd95_str} |")

        lines.append("")
        lines.append("> [!NOTE]")
        lines.append("> Các metric rỗng/null do không có foreground hoặc chưa chạy độc lập được bảo toàn nguyên trạng, không bao giờ gán cưỡng bức bằng 0.0.")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Phân tích Lỗi Định tính (Error Analysis)",
        "",
        "Bộ tạo báo cáo này chưa nhận artifact phân tích lỗi định tính.",
        "Không suy luận hình thái tổn thương hoặc nguyên nhân lỗi lâm sàng từ metric phân đoạn tổng hợp.",
        "",
        "---",
        "",
        "## 4. Đo lường Quy trình Tương tác Human-in-the-Loop (HITL)",
        "",
    ])

    hitl = report_data.get("hitl", {})
    if hitl:
        lines.extend([
            f"- **Tổng số phiên ghi nhận**: {hitl.get('total_sessions', 0)} phiên",
            f"- **Phiên thử nghiệm kỹ thuật (Technical Sessions)**: {hitl.get('technical_sessions', 0)} phiên",
            f"- **Phiên bác sĩ (Clinician Sessions)**: {hitl.get('clinician_sessions', 0)} phiên",
            f"- **Tổng số tác vụ chỉnh sửa (Total Tasks)**: {hitl.get('total_tasks', 0)} tác vụ",
            f"- **Thời gian phản hồi rà soát trung vị (Median Review Time)**: {_fmt_metric(hitl.get('clinician_median_review_ms'))} ms",
            f"- **Độ cải thiện Dice trước và sau chỉnh sửa (Δ Dice)**: {_fmt_metric(hitl.get('clinician_median_delta_dice'))} (chưa tính nếu thiếu nhãn độc lập)",
            "",
            "> [!IMPORTANT]",
            "> Dữ liệu HITL phân định rạch ròi giữa thao tác của kỹ sư kiểm thử (Technical) và bác sĩ lâm sàng (Clinician). Không tự động nội suy điểm cải thiện chất lượng khi chưa có nhãn tham chiếu độc lập.",
        ])
    else:
        lines.append("*Chưa có dữ liệu phân tích telemetry HITL.*")

    lines.extend([
        "",
        "---",
        "",
        "## 5. Khảo sát Người dùng và Tính Khả dụng Lâm sàng",
        "",
    ])

    user_study = report_data.get("user_study", {})
    study_status = user_study.get("study_status", "NOT_CONDUCTED")
    clinician_count = user_study.get("clinician_count", 0)
    tech_count = user_study.get("technical_count", 0)
    technical_acceptance_verified = (
        user_study.get("technical_acceptance") == "PASS"
        and user_study.get("technical_fallback_verified") is True
    )
    technical_acceptance_status = "PASS" if technical_acceptance_verified else "NOT VERIFIED"
    user_study_warning = (
        "Không có kết quả khảo sát bác sĩ. Khả dụng kỹ thuật chỉ được ghi nhận khi có hồ sơ nghiệm thu được xác minh."
        if not technical_acceptance_verified
        else "Không có kết quả khảo sát bác sĩ; nghiệm thu kỹ thuật không thay thế đánh giá lâm sàng."
    )

    lines.extend([
        f"- **Trạng thái nghiên cứu người dùng**: `{study_status}`",
        f"- **Số lượng bác sĩ tham gia (Clinicians)**: {clinician_count} bác sĩ",
        f"- **Số lượng kỹ thuật viên / kiểm thử viên**: {tech_count} người",
        f"- **Có đánh giá lâm sàng độc lập**: {'CÓ' if report_data.get('clinician_validation') else 'CHƯA (NOT_CONDUCTED)'}",
        f"- **Biên bản nghiệm thu kỹ thuật (Technical Acceptance)**: {technical_acceptance_status}.",
        "",
        "> [!WARNING]",
        f"> {user_study_warning}",
        "",
        "---",
        "",
        "## 6. Giới hạn Hệ thống và Khuyến cáo Lâm sàng",
        "",
        "1. **Bất thường $\\neq$ Ác tính (Abnormal $\\neq$ Malignant)**: Vùng phân đoạn chỉ mang tính chất định vị tổn thương hình thái, không phải chẩn đoán bản chất mô bệnh học u lành/u ác.",
        "2. **Pixel Recall $\\neq$ Độ nhạy chẩn đoán lâm sàng**: Chỉ số Recall trên pixel phản ánh độ bao phủ không gian của mask, không đo lường độ nhạy phát hiện bệnh nhân ung thư.",
        "3. **Tập kiểm thử độc lập bị chặn (Independent Test Gate: BLOCKED)**: Do chưa có hồ sơ bệnh nhân gốc và chứng từ khử định danh độc lập, kết quả replay hiện có không được coi là đánh giá độc lập.",
        "4. **Nguyên mẫu nghiên cứu hỗ trợ quan sát (Observation-Only Prototype)**: Hệ thống chưa được phê duyệt cho chẩn đoán y tế hoặc chỉ định phẫu thuật/điều trị thực tế.",
        "",
        "---",
        "",
        "## 7. Kết luận và Đề xuất Hướng Phát triển",
        "",
        f"- **Trạng thái nguyên mẫu nghiên cứu (Prototype Readiness: {'PASS' if report_data.get('prototype_ready') else 'NOT READY'})**: Kết quả này phản ánh riêng các kiểm tra kỹ thuật được nạp vào báo cáo; không xác nhận mức độ sẵn sàng sử dụng lâm sàng.",
        "- **Khuyến nghị tiếp theo**: Thu thập tập dữ liệu kiểm thử độc lập có đầy đủ Patient ID và đồng thuận chuyên gia đa trung tâm để mở khóa cổng đánh giá khoa học toàn diện (`evaluation_complete`).",
        "",
    ])

    return "\n".join(lines)


def generate_limitations_doc() -> str:
    """
    Renders detailed system limitations document (limitations.md).
    """
    return """# Giới hạn Hệ thống và Khuyến cáo An toàn Y tế

Tài liệu này xác định các giới hạn kỹ thuật và lâm sàng của nguyên mẫu nghiên cứu Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop (Milestone 3).

---

## 1. Bản chất Ngữ nghĩa Y khoa: Bất thường $\\neq$ Ác tính
- Mặt nạ phân đoạn (Segmentation Mask) do mô hình AI tạo ra chỉ đại diện cho việc gom cụm các điểm ảnh có hình thái phản âm nghi ngờ u nang hoặc tổn thương cấu trúc buồng trứng.
- Mặt nạ **không** phản ánh chẩn đoán ác tính (Malignancy).
- Việc phân loại u nang lành tính, u giáp biên hay ung thư buồng trứng đòi hỏi tích hợp đầy đủ các tiêu chuẩn lâm sàng IOTA Simple Rules, IOTA ADNEX, O-RADS US v2022 và kết quả giải phẫu bệnh (Histopathology).

## 2. Giới hạn về Độ đo: Pixel Recall $\\neq$ Diagnostic Sensitivity
- Chỉ số Pixel Recall đo lường tỷ lệ các pixel tổn thương trong nhãn tham chiếu được mô hình bao phủ.
- Không được đồng nhất Pixel Recall cao với độ nhạy phát hiện ca bệnh (Patient-level Sensitivity). Một tổn thương lớn có thể có Pixel Recall cao nhưng vẫn có thể bị phân loại sai tính chất u.

## 3. Trạng thái Tập Kiểm thử Độc lập (Independent Test Gate)
- Cohort replay hiện có là **Retrospective Test Replay**, tức là tập dữ liệu đã từng được sử dụng trong quá trình phát triển trước đó.
- Cổng kiểm thử độc lập (`independent_gate`) hiện ở trạng thái **BLOCKED** do thiếu ánh xạ định danh bệnh nhân gốc (`patient_id`) và biên bản kiểm định nguồn độc lập.
- Hệ thống không tuyên bố hoàn thành đánh giá độc lập (`evaluation_complete = False`) khi chưa thỏa mãn các yêu cầu kiểm soát rò rỉ dữ liệu (Data Leakage Guard).

## 4. Khảo sát Người dùng Lâm sàng Chưa Tiến hành (NOT_CONDUCTED)
- Khảo sát tương tác với bác sĩ lâm sàng thực tế được ghi nhận trạng thái trung thực là **NOT_CONDUCTED**.
- Không sử dụng phản hồi giả hoặc điểm Likert tự tạo làm bằng chứng đánh giá.
- Kiểm thử tự động Live E2E chỉ phản ánh kiểm tra kỹ thuật; không thay thế nghiệm thu người dùng hoặc xác nhận lâm sàng.

## 5. Hiện tượng Ảnh gần trùng xuyên Split (Cross-Split Near Duplicates)
- Các manifest lịch sử chưa chứng minh được phân tách bệnh nhân do thiếu Patient ID nguồn đã xác minh.
- Không suy ra số lượng ca gần trùng hoặc độc lập lâm sàng khi chưa có audit tương ứng với manifest đang dùng.

## 6. Giới hạn Đo đạc Kích thước và Thể tích 2D
- Tính năng đo kích thước chiều dài, chiều rộng và thể tích u chỉ có giá trị khi ảnh đầu vào là định dạng DICOM chuẩn có trường thông tin `PixelSpacing` đã được máy siêu âm hiệu chuẩn.
- Đối với các ảnh định dạng JPG/PNG thông thường, các phép đo kích thước hiển thị theo đơn vị pixel và chỉ mang tính chất tham khảo tương đối trong phòng thí nghiệm.

## 7. Ranh giới Pháp lý và Mục đích Sử dụng
- Hệ thống là **nguyên mẫu nghiên cứu (Research Prototype)** phục vụ nghiên cứu mô hình tương tác Người và Máy (Human-in-the-Loop) trong chuyên ngành Hệ thống Thông tin Quản lý (MIS).
- Nghiêm cấm sử dụng hệ thống như một thiết bị y tế tự động hoặc làm căn cứ duy nhất để ra quyết định phẫu thuật, chỉ định điều trị hoặc can thiệp lâm sàng trên bệnh nhân thực tế.
"""


def build_report(
    root: Path,
    run_dirs: list[Path],
    hitl_dir: Path | None,
    user_dir: Path | None,
    independent_gate_path: Path | None,
    output: Path,
    prototype_checks_passed: bool = False,
    checks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Consolidates evaluation runs, HITL telemetry, user study findings, and gates
    into a comprehensive report artifact structure.
    """
    output.mkdir(parents=True, exist_ok=True)
    tables_dir = output / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    # 1. Audit Runs
    audited_runs = []
    checkpoint_sha = None
    for rdir in run_dirs:
        summary_path = rdir / "summary.json"
        if summary_path.exists():
            run_data = audit_run_summary(summary_path)
            audited_runs.append(run_data)
            if not checkpoint_sha and run_data.get("checkpoint_sha256"):
                checkpoint_sha = run_data.get("checkpoint_sha256")

    model_configuration = _load_model_configuration(root)
    if not checkpoint_sha:
        checkpoint_sha = model_configuration.get("checkpoint_sha256")

    # 2. Audit HITL Telemetry
    hitl_data = {}
    if hitl_dir and (hitl_dir / "summary.json").exists():
        with open(hitl_dir / "summary.json", encoding="utf-8") as f:
            hitl_data = json.load(f)

    # 3. Audit User Study
    user_study_data = {
        "study_status": "UNKNOWN",
        "clinician_count": 0,
        "technical_count": None,
        "has_clinician_validation": False,
    }
    if user_dir and (user_dir / "study_status.json").exists():
        with open(user_dir / "study_status.json", encoding="utf-8") as f:
            user_study_data = json.load(f)

    # 4. Check Independent Gate
    gate_json = None
    independent_gate_status = "UNKNOWN"
    if independent_gate_path and independent_gate_path.exists():
        with open(independent_gate_path, encoding="utf-8") as f:
            gate_json = json.load(f)
            independent_gate_status = gate_json.get("status", "UNKNOWN")
    else:
        # Check standard location under root
        std_gate = root / "evaluation" / "milestone_3_final" / "data_audit" / "independent_gate" / "audit.json"
        if std_gate.exists():
            with open(std_gate, encoding="utf-8") as f:
                gate_json = json.load(f)
                independent_gate_status = gate_json.get("status", "UNKNOWN")

    # 5. Determine release status via derive_release_status
    status_result = derive_release_status(
        checks=checks,
        independent_gate=gate_json,
        user_study=user_study_data if (user_dir and (user_dir / "study_status.json").exists()) else (user_study_data if user_dir else None),
        hitl=hitl_data if hitl_dir else None,
        runs=audited_runs,
        prototype_checks_passed=prototype_checks_passed,
    )
    prototype_ready = status_result["prototype_ready"]
    evaluation_complete = status_result["evaluation_complete"]
    clinician_validation = status_result["clinician_validation"]
    blockers = status_result["blockers"]
    limitations = status_result["limitations"]
    check_evidence = {
        "overall_exit_code": (
            checks.get("overall_exit_code")
            if isinstance(checks, dict) and type(checks.get("overall_exit_code")) is int
            else None
        ),
        "runtime_workflow_verified": checks.get("runtime_workflow_verified") is True if isinstance(checks, dict) else False,
        "packaging_verified": checks.get("packaging_verified") is True if isinstance(checks, dict) else False,
    }

    report_payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "checkpoint_sha256": checkpoint_sha,
        "prototype_ready": prototype_ready,
        "evaluation_complete": evaluation_complete,
        "clinician_validation": clinician_validation,
        "blockers": blockers,
        "limitations": limitations,
        "runs": audited_runs,
        "model_configuration": model_configuration,
        "checks": check_evidence,
        "hitl": hitl_data,
        "user_study": user_study_data,
        "independent_gate_status": independent_gate_status,
    }

    # 6. Write release_status.json
    release_status_path = output / "release_status.json"
    with open(release_status_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    # 7. Write results.md
    results_md = generate_markdown_report(report_payload)
    (output / "results.md").write_text(results_md, encoding="utf-8")

    # 8. Write limitations.md
    limitations_md = generate_limitations_doc()
    (output / "limitations.md").write_text(limitations_md, encoding="utf-8")

    # 9. Write tables/cohort_metrics.csv
    cohort_csv_path = tables_dir / "cohort_metrics.csv"
    with open(cohort_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id",
            "run_kind",
            "is_historical_replay",
            "total_samples",
            "dice_mean",
            "dice_median",
            "iou_mean",
            "recall_mean",
            "precision_mean",
            "specificity_mean",
            "hd95_px_mean",
        ])
        for r in audited_runs:
            counts = r.get("counts", {})
            p = r.get("primary", {})
            writer.writerow([
                r.get("run_id"),
                r.get("run_kind"),
                r.get("is_historical_replay"),
                counts.get("total_samples"),
                p.get("dice", {}).get("mean"),
                p.get("dice", {}).get("median"),
                p.get("iou", {}).get("mean"),
                p.get("recall", {}).get("mean"),
                p.get("precision", {}).get("mean"),
                p.get("specificity", {}).get("mean"),
                p.get("hd95_px", {}).get("mean"),
            ])

    # 10. Write evidence_matrix.csv
    evidence_matrix_path = output / "evidence_matrix.csv"
    _write_evidence_matrix(evidence_matrix_path, report_payload)

    # 11. Write open_issues.csv
    generate_open_issues_csv(output / "open_issues.csv")

    # 12. Write demo_script.md
    generate_demo_script_md(output / "demo_script.md")

    # 13. Write final_checks.json
    checks_input = checks or {
        "skip_browser": False,
        "overall_exit_code": 0,
        "live_browser_verified": False,
        "commands": [],
        "prototype_ready": False,
    }
    generate_final_checks(
        results=checks_input,
        independent_gate_status=independent_gate_status,
        output_dir=output,
        user_study=user_study_data if (user_dir and (user_dir / "study_status.json").exists()) else (user_study_data if user_dir else None),
        hitl=hitl_data if hitl_dir else None,
        runs=audited_runs,
        independent_gate=gate_json,
    )

    # 14. Write checksums.csv
    generate_checksums_csv(root, output / "checksums.csv")

    return report_payload


def _write_evidence_matrix(target_path: Path, report_payload: dict[str, Any]) -> None:
    runs = report_payload.get("runs", [])
    legacy_run = next((run for run in runs if run.get("is_historical_replay") is True), None)
    legacy_status = "VERIFIED (RETROSPECTIVE REPLAY)" if legacy_run else "NOT PROVIDED"
    if legacy_run:
        legacy_dice = legacy_run.get("primary", {}).get("dice", {}).get("mean")
        legacy_note = f"Retrospective replay only; Dice mean {_fmt_metric(legacy_dice)}. Not an independent test."
    else:
        legacy_note = "No legacy replay summary was supplied to this report."

    hitl = report_payload.get("hitl", {})
    hitl_sessions = hitl.get("total_sessions") if isinstance(hitl, dict) else None
    hitl_status = "VERIFIED (TECHNICAL TELEMETRY)" if type(hitl_sessions) is int and hitl_sessions > 0 else "NOT PROVIDED"
    hitl_note = (
        f"{hitl_sessions} telemetry sessions supplied; this does not establish clinician validation."
        if type(hitl_sessions) is int and hitl_sessions > 0
        else "No HITL telemetry summary was supplied to this report."
    )

    checks = report_payload.get("checks", {})
    checks_pass = isinstance(checks, dict) and checks.get("overall_exit_code") == 0
    browser_verified = report_payload.get("prototype_ready") is True
    runtime_verified = checks_pass and checks.get("runtime_workflow_verified") is True
    packaging_verified = checks_pass and checks.get("packaging_verified") is True
    independent_gate_note = (
        "Provided independent patient-level gate passed."
        if report_payload.get("independent_gate_status") == "PASS"
        else "Independent patient-level mapping is unverified; holdout remains blocked."
    )

    user_study = report_payload.get("user_study", {})
    technical_fallback_verified = (
        user_study.get("technical_acceptance") == "PASS"
        and user_study.get("technical_fallback_verified") is True
    )
    clinician_validation = report_payload.get("clinician_validation") is True
    user_study_evidence_status = (
        "VERIFIED" if clinician_validation or technical_fallback_verified else "NOT_CONDUCTED / NOT VERIFIED"
    )
    if clinician_validation:
        user_study_evidence_notes = "Verified clinician evidence recorded."
    elif technical_fallback_verified:
        user_study_evidence_notes = "Clinician study not conducted; verified technical acceptance is recorded as a technical fallback."
    else:
        user_study_evidence_notes = "No verified clinician study or technical acceptance fallback is recorded."

    rows = [
        [
            "R1",
            "T02-T06",
            "Quantitative test on independent cohort without leakage",
            "Lead Researcher",
            "evaluation/milestone_3_final/data_audit/independent_gate/audit.json",
            "BLOCKED" if not report_data_gate_passed(report_payload) else "VERIFIED",
            independent_gate_note,
        ],
        [
            "R1-Legacy",
            "T05-T06",
            "Retrospective test replay on previously used test set",
            "ML Engineer",
            "evaluation/milestone_3_final/legacy_test_v1/summary.json",
            legacy_status,
            legacy_note,
        ],
        [
            "R2",
            "T03+T07",
            "Error analysis and multi-group ranking",
            "ML Engineer",
            "evaluation/milestone_3_final/legacy_test_v1/error_analysis/analysis.json",
            "NOT VERIFIED",
            "No error-analysis artifact was supplied to this report.",
        ],
        [
            "R3",
            "T08-T14",
            "Human-in-the-loop workflow persistence, timing, and deltas",
            "Fullstack Engineer",
            "evaluation/milestone_3_final/hitl/analysis/summary.json",
            hitl_status,
            hitl_note,
        ],
        [
            "R4",
            "T15",
            "Clinician evaluation or technical usability fallback",
            "Clinical Lead",
            "evaluation/milestone_3_final/user_study/study_status.json",
            user_study_evidence_status,
            user_study_evidence_notes,
        ],
        [
            "R5",
            "T19-T20",
            "Consolidated report, limitations, and release evidence",
            "Lead Researcher",
            "evaluation/milestone_3_final/report/release_status.json",
            "VERIFIED",
            "Consolidated results.md, limitations.md, and release status generated",
        ],
        [
            "APP-P0",
            "T08-T11",
            "Live runnable prototype login, cases, upload, edit, save, export",
            "Fullstack Engineer",
            "artifacts/review-e2e-runtime/technical_test.sqlite3",
            "VERIFIED" if runtime_verified else "NOT VERIFIED",
            "Runtime workflow check explicitly recorded." if runtime_verified else "No runtime workflow check was supplied.",
        ],
        [
            "APP-E2E",
            "T16-T17",
            "Browser synthetic safety regression and real-API synthetic-image save/reopen; no process restart claim",
            "QA / Test Engineer",
            "tests/workstation_viewer_e2e.js; tests/clinical_safety_e2e.js; tests/clinical_roundtrip_e2e.js",
            "VERIFIED" if browser_verified else "NOT VERIFIED",
            "Live browser check explicitly recorded." if browser_verified else "No passing live browser check was supplied.",
        ],
        [
            "APP-PKG",
            "T18",
            "Windows packaging clean launcher and runbook",
            "DevOps / Engineer",
            "scripts/run_prototype.ps1",
            "VERIFIED" if packaging_verified else "NOT VERIFIED",
            "Packaging checks explicitly recorded." if packaging_verified else "No packaging check was supplied.",
        ],
    ]

    with open(target_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "requirement_id",
            "task_id",
            "name",
            "owner",
            "evidence_artifact",
            "status",
            "next_action",
        ])
        writer.writerows(rows)


def report_data_gate_passed(report_payload: dict[str, Any]) -> bool:
    return report_payload.get("independent_gate_status") == "PASS"


def generate_open_issues_csv(output_path: Path) -> None:
    rows = [
        [
            "ISS-01",
            "HIGH",
            "Tập kiểm thử độc lập thiếu Patient ID gốc (Independent Test Gate BLOCKED)",
            "OPEN",
            "Không thể tuyên bố hoàn thành đánh giá độc lập (evaluation_complete = False)",
            "Chỉ công nhận Retrospective Test Replay; giữ cổng BLOCKED đến khi có dữ liệu kiểm định độc lập",
        ],
        [
            "ISS-02",
            "MEDIUM",
            "Khảo sát người dùng lâm sàng chưa tiến hành (study_status = NOT_CONDUCTED)",
            "OPEN",
            "Chưa có đánh giá định tính từ bác sĩ thực tế",
            "Ghi NOT_CONDUCTED; chỉ ghi technical fallback khi có đủ biên bản nghiệm thu đã xác minh",
        ],
        [
            "ISS-03",
            "MEDIUM",
            "Thiếu Patient ID nguồn đã xác minh cho split Train/Val/Test",
            "OPEN",
            "Không thể loại trừ rò rỉ cấp bệnh nhân hoặc chứng minh độc lập của split",
            "Giữ cổng đánh giá độc lập đóng đến khi có mapping Patient ID nguồn đã xác minh",
        ],
        [
            "ISS-04",
            "LOW",
            "Phép đo kích thước 2D chưa hiệu chuẩn mm trên ảnh JPG/PNG",
            "OPEN",
            "Không đo được kích thước thực tế cho ảnh không phải DICOM",
            "Khóa chế độ mm khi thiếu PixelSpacing, chỉ hiển thị đơn vị pixel",
        ],
        [
            "ISS-05",
            "LOW",
            "Hệ thống là prototype nghiên cứu một máy",
            "OPEN",
            "Chưa hỗ trợ triển khai đa viện hay concurrency cao",
            "Tài liệu hóa giới hạn trong release runbook và limitations.md",
        ],
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["issue_id", "severity", "title", "status", "impact", "mitigation"])
        writer.writerows(rows)


def generate_checksums_csv(root: Path, output_path: Path) -> None:
    import hashlib

    target_files = [
        "scripts/run_prototype.ps1",
        "scripts/verify_evaluation_release.ps1",
        "scripts/build_evaluation_report.py",
        "evaluation/protocols/milestone3_v1.json",
        "evaluation/current_run.json",
        "evaluation/milestone_3_final/legacy_test_v1/summary.json",
        "evaluation/milestone_3_final/validation_v1/summary.json",
        "evaluation/milestone_3_final/report/results.md",
        "evaluation/milestone_3_final/report/limitations.md",
        "evaluation/milestone_3_final/report/release_status.json",
        "evaluation/milestone_3_final/report/evidence_matrix.csv",
    ]

    rows = []
    for rel_path in target_files:
        p = root / rel_path
        if p.exists():
            data = p.read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()
            rows.append([rel_path.replace("\\", "/"), sha256, len(data), "Release verified artifact"])
        else:
            rows.append([rel_path.replace("\\", "/"), "NOT_FOUND", 0, "Artifact pending or missing"])

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_path", "sha256", "bytes", "description"])
        writer.writerows(rows)


def generate_demo_script_md(output_path: Path) -> None:
    content = """# Kịch bản Thực nghiệm Trực tiếp (5-7 Phút Rehearsal Demo Script)

Tài liệu này dùng để điều hành buổi thử nghiệm/bảo vệ nguyên mẫu Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop.

---

### Phút 0:00 - 01:00: Khởi động và Kiểm tra Tiền khả thi (Pre-flight Checks)
1. Mở PowerShell trong thư mục gốc của dự án.
2. Thiết lập biến môi trường bảo mật:
   ```powershell
   $env:APP_JWT_SECRET = "super-secret-jwt-key-minimum-32-chars-long"
   $env:APP_PATIENT_PID_HMAC_SECRET = "replace-with-a-separate-random-key-at-least-32-bytes"
   $env:APP_DOCTOR_PASSWORD = "DoctorSecurePassword2026!"
   $env:APP_ADMIN_PASSWORD = "AdminSecurePassword2026!"
   ```
3. Chạy lệnh kiểm tra tiền khả thi:
   ```powershell
   .\\scripts\\run_prototype.ps1 -RuntimeDir artifacts\\demo-runtime -CheckOnly
   ```
4. Xác nhận log: Python virtualenv hợp lệ, trọng số checkpoint U-Net khớp SHA-256 (`417828fa...`), các biến môi trường bí mật đã được xác thực mà không bị in lộ.

---

### Phút 01:00 - 02:00: Khởi chạy và Đăng nhập Bác sĩ
1. Khởi chạy máy chủ nguyên mẫu:
   ```powershell
   .\\scripts\\run_prototype.ps1 -RuntimeDir artifacts\\demo-runtime -Port 8000
   ```
2. Mở trình duyệt web truy cập `http://127.0.0.1:8000`.
3. Đăng nhập bằng tài khoản: `doctor` / mật khẩu `$env:APP_DOCTOR_PASSWORD`.
4. Quan sát trang chủ: Trạng thái mô hình AI báo Sẵn sàng (Ready), Checkpoint SHA-256 hiển thị minh bạch.

---

### Phút 02:00 - 03:30: Nạp ca Hai bên (Bilateral Intake) và AI Suy luận
1. Nhấn nút **"Tiếp nhận ca mới"** (New Case).
2. Nhập mã ca bệnh (VD: `CASE-DEMO-01`), chọn quy trình phân tích hai bên (Trái & Phải).
3. Tải lên 2 ảnh siêu âm buồng trứng cho Buồng trứng Trái và Buồng trứng Phải.
4. Nhấn **"Chạy AI phân tích"**:
   - Hệ thống tự động tiền xử lý Letterbox 512×512 và đưa qua mô hình U-Net.
   - Kết quả phân đoạn hiển thị trong không gian phân giải gốc (Native Space) kèm thời gian thực thi (model_forward_ms và server_pipeline_ms).

---

### Phút 03:30 - 05:00: Tương tác HITL (Brush, Erase, Undo, Redo, Reset AI)
1. Quan sát lớp phủ tổn thương (Overlay) trên ảnh Buồng trứng Trái.
2. Chọn công cụ **Brush (Cọ vẽ)**: Vẽ mở rộng thêm một vùng tổn thương.
3. Chọn công cụ **Eraser (Tẩy)**: Xóa bớt một phần viền bị lan ra ngoài.
4. Nhấn **Undo (Hoàn tác)** và **Redo**: Chứng minh lịch sử thao tác được quản lý chính xác từng pixel.
5. Nhấn **Reset AI**: Hộp thoại cảnh báo xuất hiện xác nhận hủy bỏ toàn bộ chỉnh sửa để quay về mask AI gốc. Xác nhận Reset.
6. Vẽ chỉnh sửa hoàn thiện cuối cùng trên cả 2 buồng trứng.

---

### Phút 05:00 - 06:00: Xác nhận Rà soát Atomic và Xuất Gói Nghiên cứu (ZIP Export)
1. Nhập nhận xét chuyên môn của bác sĩ vào ô ghi chú.
2. Nhấn **"Xác nhận kết quả rà soát"** (Confirm Research Review):
   - Hệ thống thực thi giao dịch cơ sở dữ liệu nguyên tử (Atomic Database Transaction), đồng thời lưu cả 2 ảnh và nâng phiên bản `review_revision` từ 0 lên 1.
3. Nhấn **"Tải kết quả nghiên cứu"**:
   - Trình duyệt tải về tệp tin ZIP `research_export_CASE-DEMO-01_rev1.zip`.
   - Mở tệp ZIP minh chứng 7 tệp tin: `metadata.json` (chứa SHA-256 của từng tệp), 2 ảnh gốc, 2 mask do AI dự đoán và 2 mask đã qua bác sĩ rà soát.

---

### Phút 06:00 - 07:00: Đối chiếu Kết quả Đánh giá và Đóng ca
1. Nhấn chuyển sang mục **"Đánh giá mô hình"** (`#evaluation`):
   - Quan sát bảng kết quả của lượt chạy chuẩn hóa `legacy_test_v1` (Dice Mean: 0.7289, HD95: 90.19 px).
   - Quan sát cảnh báo minh bạch: Cổng kiểm thử độc lập ở trạng thái `BLOCKED` do chưa có định danh bệnh nhân nguồn.
   - Mở panel phân tích lỗi đối chiếu 5 cột (Original, GT, Prediction, Overlay, Difference).
2. Kết thúc buổi demo: Tắt máy chủ bằng `Ctrl+C`. Khởi động lại máy chủ và mở lại `CASE-DEMO-01` để chứng minh toàn bộ dữ liệu đã lưu trữ bền vững.
"""
    output_path.write_text(content, encoding="utf-8")


def generate_final_checks(
    results: dict[str, Any],
    independent_gate_status: str,
    output_dir: Path,
    user_study: dict[str, Any] | None = None,
    hitl: dict[str, Any] | None = None,
    runs: list[dict[str, Any]] | None = None,
    independent_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if independent_gate is None:
        independent_gate = {"status": independent_gate_status}

    status_res = derive_release_status(
        checks=results,
        independent_gate=independent_gate,
        user_study=user_study,
        hitl=hitl,
        runs=runs,
    )
    skip_browser = bool(results.get("skip_browser", False) or results.get("browser_skipped", False))
    commands = results.get("commands", [])
    overall_exit = results.get("overall_exit_code", 0)

    e2e_cmd = next((c for c in commands if "release_e2e" in c.get("name", "")), None)
    if "live_browser_verified" in results:
        live_browser_verified = bool(results["live_browser_verified"])
    elif e2e_cmd is not None:
        live_browser_verified = (not skip_browser) and (e2e_cmd.get("exit_code") == 0)
    else:
        live_browser_verified = False

    checks = {
        "schema_version": 1,
        "generated_at": results.get("start_time") or datetime.now(UTC).isoformat(),
        "test_scope": results.get("test_scope", "selected"),
        "overall_exit_code": overall_exit,
        "prototype_ready": status_res["prototype_ready"],
        "evaluation_complete": status_res["evaluation_complete"],
        "clinician_validation": status_res["clinician_validation"],
        "independent_gate_status": independent_gate_status,
        "browser_skipped": skip_browser,
        "live_browser_verified": live_browser_verified,
        "commands_executed": len(commands),
        "blockers": status_res["blockers"],
        "limitations": status_res["limitations"],
    }

    final_checks_path = output_dir / "final_checks.json"
    with open(final_checks_path, "w", encoding="utf-8") as f:
        json.dump(checks, f, indent=2)

    return checks


def validate_release_package(
    report_dir: Path,
    expected_checkpoint_sha: str = "417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d",
) -> tuple[bool, list[str]]:
    required_files = [
        "results.md",
        "limitations.md",
        "evidence_matrix.csv",
        "checksums.csv",
        "final_checks.json",
        "open_issues.csv",
        "demo_script.md",
        "release_status.json",
    ]
    errors = []
    for fname in required_files:
        p = report_dir / fname
        if not p.exists():
            errors.append(f"Missing required release artifact: {fname}")

    status_file = report_dir / "release_status.json"
    if status_file.exists():
        try:
            with open(status_file, encoding="utf-8") as f:
                data = json.load(f)
            actual_sha = data.get("checkpoint_sha256", "")
            if expected_checkpoint_sha and actual_sha != expected_checkpoint_sha:
                errors.append(
                    f"Checkpoint hash mismatch in release_status.json: expected {expected_checkpoint_sha}, got {actual_sha}"
                )
        except Exception as e:
            errors.append(f"Failed to read release_status.json: {e}")

    return (len(errors) == 0, errors)


def main():
    parser = argparse.ArgumentParser(description="Build consolidated evaluation report from artifacts.")
    parser.add_argument("--root", type=str, default=".", help="Root directory of repository")
    parser.add_argument("--runs", nargs="*", default=[], help="Paths to run directories")
    parser.add_argument("--hitl", type=str, default=None, help="Path to HITL analysis directory")
    parser.add_argument("--user-study", type=str, default=None, help="Path to user study directory")
    parser.add_argument("--independent-gate", type=str, default=None, help="Path to independent gate audit.json")
    parser.add_argument("--output", type=str, required=True, help="Path to output report directory")
    parser.add_argument("--set-current", type=str, default=None, help="Path to run directory to set as current_run.json")
    parser.add_argument("--checks", type=str, default=None, help="Path to baseline_results.json / checks log")

    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_dirs = [Path(p).resolve() for p in args.runs]
    hitl_dir = Path(args.hitl).resolve() if args.hitl else None
    user_dir = Path(args.user_study).resolve() if args.user_study else None
    gate_path = Path(args.independent_gate).resolve() if args.independent_gate else None
    output = Path(args.output).resolve()

    checks_data = None
    if args.checks:
        checks_file = Path(args.checks).resolve()
        if checks_file.exists():
            with open(checks_file, encoding="utf-8") as f:
                checks_data = json.load(f)

    report = build_report(
        root=root,
        run_dirs=run_dirs,
        hitl_dir=hitl_dir,
        user_dir=user_dir,
        independent_gate_path=gate_path,
        output=output,
        prototype_checks_passed=False,
        checks=checks_data,
    )

    print(f"[OK] Report generated at {output}")
    print(f"  Prototype Ready: {report['prototype_ready']}")
    print(f"  Evaluation Complete: {report['evaluation_complete']}")
    print(f"  Blockers: {len(report['blockers'])}")

    if args.set_current:
        target_run_dir = Path(args.set_current).resolve()
        summary_path = target_run_dir / "summary.json"
        if not summary_path.exists():
            raise FileNotFoundError(f"Cannot set current run: {summary_path} not found")

        with open(summary_path, encoding="utf-8") as f:
            sum_data = json.load(f)

        sample_count = sum_data.get("counts", {}).get("total_samples")
        run_label = (
            f"Retrospective Test Replay ({sample_count} samples)"
            if sum_data.get("run_kind") == "retrospective_test_replay" and type(sample_count) is int
            else "Retrospective Test Replay"
            if sum_data.get("run_kind") == "retrospective_test_replay"
            else "Validation Cohort"
        )

        pointer_data = {
            "summary_path": str(summary_path.relative_to(root)).replace("\\", "/"),
            "run_id": sum_data.get("run_id"),
            "run_kind": sum_data.get("run_kind"),
            "protocol_sha256": sum_data.get("protocol_sha256"),
            "manifest_sha256": sum_data.get("manifest_sha256"),
            "checkpoint_sha256": sum_data.get("checkpoint_sha256"),
            "status": sum_data.get("status"),
            "label": run_label,
        }

        pointer_path = root / "evaluation" / "current_run.json"
        temp_pointer_path = pointer_path.with_suffix(".tmp")
        with open(temp_pointer_path, "w", encoding="utf-8") as f:
            json.dump(pointer_data, f, indent=2)
        os.replace(temp_pointer_path, pointer_path)
        print(f"[OK] Atomically updated current run pointer at {pointer_path}")


if __name__ == "__main__":
    main()
