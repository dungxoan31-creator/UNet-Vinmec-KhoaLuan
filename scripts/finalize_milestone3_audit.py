"""Preserve document versions and publish evidence-grounded Milestone 3 status."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.audit_milestone3_evidence import ROOT, rows, sha, write_json

OUTPUT = ROOT / "evaluation/milestone_3_audit_2026-10-06"
LOCK_DIR = OUTPUT / "validation_lock"


def review_documents():
    import scripts.export_milestone2_report as exporter

    source = OUTPUT / "document_backups/docs/reports/Bao_Cao_Tien_Do_Moc_2_NguyenHuuDung_2026-10-03.md"
    text = source.read_text(encoding="utf-8")
    text = text.replace("(assets/", "(../../docs/reports/assets/")
    text = text.replace(
        "Test Specificity — 5 bản ghi mask rỗng theo định nghĩa của Mốc 1",
        "Historical Pixel Specificity — 5 bản ghi có mask dẫn xuất toàn 0 theo Mốc 1",
    )
    text = text.replace(
        "Thống nhất checkpoint tích hợp với checkpoint Mốc 1 trước khi công bố prototype là đang chạy chính mô hình baseline Mốc 1; sau khi thay đổi cần lưu SHA và chạy lại kiểm tra nạp/suy diễn.",
        "Ghi riêng checkpoint tích hợp lịch sử 5e14be… với checkpoint baseline Mốc 1; kiểm thử nạp/suy diễn là bằng chứng kỹ thuật, không chứng minh metric của hai checkpoint giống nhau.",
    )
    text += "\n\n## Ghi chú rà soát ngày 06/10/2026 — không thay đổi số liệu lịch sử\n\n"
    text += (
        "Bản này là phiên bản reviewed, xuất từ snapshot Git của bản Mốc 2 sau khi file working tree bị xóa. "
        "Các số liệu baseline và 61 passed ngày 04/10 giữ vai trò historical result; command gốc không có trong log. "
        "Hiện bộ Mốc 1 không có tại đường dẫn khai báo; full suite mới ghi 67 passed / 8 failed. "
        "Chủ dự án yêu cầu tiếp tục với Vinmec_2d và Vinmec_3d; các thử nghiệm Mốc 3 và model lock U-Net++ được báo riêng. "
        "Patient-level independence và phê duyệt nhãn chuyên gia chưa xác minh. 35 fallback không được xem là Ground Truth hay ca âm tính.\n"
    )
    reviewed = OUTPUT / "m2_report_reviewed.md"
    reviewed.write_text(text, encoding="utf-8")
    exporter.SOURCE = reviewed
    exporter.OUTPUT = OUTPUT / "BaoCaoTienDoMoc2_NguyenHuuDung_11235559_reviewed_2026-10-06.docx"
    exporter.export()
    # Use the same existing Word renderer for the full audit; preserve the original M2 files in backups.
    exporter.SOURCE = ROOT / "docs/reports/Kiem_Toan_Moc_3_2026-10-06.md"
    exporter.OUTPUT = ROOT / "docs/reports/Kiem_Toan_Moc_3_2026-10-06.docx"
    exporter.export()
    status = json.loads((ROOT / "docs/project_status.json").read_text(encoding="utf-8"))
    source_inventory = json.loads((OUTPUT / "two_source_inventory.json").read_text(encoding="utf-8"))
    m3 = status["milestone_3"]
    m3["owner_requested_active_sources"] = source_inventory["owner_requested_scope"]
    m3["active_two_source_index"] = source_inventory["index"]
    m3["active_two_source_index_sha256"] = source_inventory["index_sha256"]
    m3["active_two_source_counts"] = source_inventory["counts"]
    m3["scope_change_note"] = (
        "Owner confirmed continuation with two Vinmec source folders; all frozen canonical samples already reside there. Historical duplicate folders and M2 files remain absent; no raw data or split was recreated."
    )
    status["milestone_2"]["reviewed_report_docx"] = (
        (OUTPUT / "BaoCaoTienDoMoc2_NguyenHuuDung_11235559_reviewed_2026-10-06.docx").relative_to(ROOT).as_posix()
    )
    write_json(ROOT / "docs/project_status.json", status)
    print("Exported reviewed M2 and full audit DOCX; active scope/index recorded")


def verify():
    inventory = rows(OUTPUT / "evidence_inventory.csv")
    protected = [
        r
        for r in inventory
        if r["artifact_type"] in {"checkpoints", "ai_training/splits"}
        or (r["artifact_type"] == "evaluation" and Path(r["path"]).suffix in {".json", ".csv"})
    ]
    changed = [r["path"] for r in protected if not (ROOT / r["path"]).is_file() or sha(ROOT / r["path"]) != r["sha256"]]
    index = rows(OUTPUT / "active_two_source_index.csv")
    source_changed = [
        r["image_path"]
        for r in index
        if sha(ROOT / r["image_path"]) != r["sample_id"] or sha(ROOT / r["mask_path"]) != r["mask_sha256"]
    ]
    before = json.loads((OUTPUT / "verified_data/dataset_audit.json").read_text(encoding="utf-8"))["protected_hashes"]
    split_changes = [name for name, digest in before.items() if sha(ROOT / name) != digest]
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    (OUTPUT / "git_diff_check.txt").write_text(diff.stdout + diff.stderr, encoding="utf-8")
    state = subprocess.check_output(["git", "status", "--short"], cwd=ROOT).decode("utf-8")
    (OUTPUT / "git_status_final.txt").write_text(state, encoding="utf-8")
    (OUTPUT / "git_diff_stat.txt").write_text(
        subprocess.check_output(["git", "diff", "--stat"], cwd=ROOT).decode("utf-8"), encoding="utf-8"
    )
    write_json(
        OUTPUT / "final_checks.json",
        {
            "checked_at": datetime.now(UTC).isoformat(),
            "command": "python scripts/finalize_milestone3_audit.py verify",
            "protected_artifact_count": len(protected),
            "protected_artifact_changes": changed,
            "source_image_target_pairs_checked": len(index),
            "source_pair_changes": source_changed,
            "frozen_split_changes": split_changes,
            "git_diff_check_exit": diff.returncode,
            "full_suite_pass": False,
            "latest_test_result": "67 passed / 8 failed; legacy M1 data missing",
            "historical_source_path_limitations": "reported separately; not restored or hidden",
            "no_selected_model_test_inference_during_audit": True,
            "readiness": "not_fully_ready",
        },
    )
    print(
        json.dumps(
            {
                "protected_artifacts": len(protected),
                "protected_changes": changed,
                "source_changes": source_changed,
                "split_changes": split_changes,
                "diff_check_exit": diff.returncode,
            }
        )
    )


def main():
    backup = OUTPUT / "document_backups"
    backup.mkdir(exist_ok=False)
    inventory = {r["path"]: r for r in rows(OUTPUT / "evidence_inventory.csv")}
    names = [
        "README.md",
        "MODEL_CARD.md",
        "TECH_STACK.md",
        "docs/project_status.json",
        "docs/reports/Bao_Cao_Tien_Do_Moc_3_NguyenHuuDung_2026-10-06.md",
        "docs/reports/Bieu_Mau_Danh_Gia_HITL_Moc_3.md",
    ]
    archived = []
    for name in names:
        source = ROOT / name
        if sha(source) != inventory[name]["sha256"]:
            raise ValueError(f"Concurrent modification; refusing to overwrite {name}")
        target = backup / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        archived.append(
            {
                "path": name,
                "backup": target.relative_to(ROOT).as_posix(),
                "sha256": sha(target),
                "source": "pre_edit_working_tree",
            }
        )
    for name in (
        "dataset/index.csv",
        "docs/reports/BaoCaoTienDoMoc2_NguyenHuuDung_11235559_final.docx",
        "docs/reports/Bao_Cao_Tien_Do_Moc_2_NguyenHuuDung_2026-10-03.md",
        "docs/reports/Bao_Cao_Tien_Do_Moc_2_NguyenHuuDung_Final.docx",
    ):
        blob = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT)
        target = backup / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        archived.append(
            {
                "path": name,
                "backup": target.relative_to(ROOT).as_posix(),
                "sha256": sha(target),
                "source": "HEAD_snapshot; working_tree_file_disappeared_during_audit; not_restored_over_user_deletion",
            }
        )
    write_json(OUTPUT / "document_backups.json", {"created_at": datetime.now(UTC).isoformat(), "files": archived})

    status = json.loads((ROOT / "docs/project_status.json").read_text(encoding="utf-8"))
    latest = json.loads((LOCK_DIR / "pytest_latest.json").read_text(encoding="utf-8"))
    lock = json.loads((LOCK_DIR / "model_lock.json").read_text(encoding="utf-8"))
    status["as_of"] = datetime.now(UTC).isoformat()
    status["current_state"] = "milestone_3_not_fully_ready_evidence_and_missing_data_blockers"
    status["milestone_2"]["automated_test_suite_at_milestone_2"] = (
        "61 passed; historical log evaluation/milestone_2_m1_scope/pytest_2026-10-04.txt; original command not recorded in log"
    )
    status["milestone_2"]["readable_pairs_status"] = "307 was historical; current 307 paths unavailable"
    status["milestone_2"]["report_current_status"] = (
        "official_DOCX_identified_at_initial_inventory; currently_deleted_in_working_tree; exact_HEAD_copy_in_audit_document_backups"
    )
    m3 = status["milestone_3"]
    m3["status"] = "partially_ready; software_regression_and_source_evidence_blockers"
    m3["automated_tests"] = f"{latest['counts']['passed']} passed, {latest['counts']['failed']} failed"
    m3["latest_test_run"] = latest
    m3["previous_test_count_claim"] = (
        "75 passed in previous project_status; 74/74 in previous M3 report; no timestamped raw log for either found in initial inventory"
    )
    m3["frozen_research_model"] = {
        "manifest": (LOCK_DIR / "model_lock.json").relative_to(ROOT).as_posix(),
        "checkpoint_sha256": lock["checkpoint_sha256"],
        "test_evaluation": None,
        "validation_verification": (LOCK_DIR / "validation_summary.json").relative_to(ROOT).as_posix(),
        "error_analysis": (LOCK_DIR / "error_analysis_summary.json").relative_to(ROOT).as_posix(),
        "browser_smoke": (LOCK_DIR / "browser_smoke_run.json").relative_to(ROOT).as_posix(),
        "latency": (LOCK_DIR / "api_latency_summary.json").relative_to(ROOT).as_posix(),
    }
    m3["default_deployed_checkpoint_sha256"] = json.loads(
        (ROOT / "evaluation/selected_model.json").read_text(encoding="utf-8")
    )["checkpoint_sha256"]
    m3["test_interpretation"] = (
        "evaluation on previously used Test set; historical Standard U-Net only; not a blind independent patient-level evaluation"
    )
    m3["readiness_blockers"] = [
        "source Patient/Case mapping unavailable",
        "expert reference-label approval unavailable",
        "no new verified independent cohort",
        "missing M1 dataset paths causing 8 test failures",
        "dataset/index.csv and official M2 documents deleted during audit by an unidentified external action",
    ]
    m3["clinical_hitl"] = (
        "not_performed_or_not_verified; no real participant results found; optional if access unavailable, disclose limitation"
    )
    m3["audit_report"] = "docs/reports/Kiem_Toan_Moc_3_2026-10-06.md"
    write_json(ROOT / "docs/project_status.json", status)
    print("Backed up", len(archived), "files; project status now reflects latest evidence")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "review-documents":
        review_documents()
    elif len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify()
    else:
        main()
