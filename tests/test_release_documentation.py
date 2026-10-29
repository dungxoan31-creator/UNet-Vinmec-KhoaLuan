import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_readme_release_runbook_link_resolves():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme)
    runbook_links = [link for link in links if link == "docs/evaluation/release_runbook.md"]

    assert runbook_links, "README must link to the release runbook."
    assert (PROJECT_ROOT / runbook_links[0]).is_file()


def test_local_links_in_readme_and_runbook_resolve():
    documents = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs/evaluation/release_runbook.md",
    ]
    for document in documents:
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8"))
        for link in links:
            if "://" in link or link.startswith("#"):
                continue
            target = link.split("#", maxsplit=1)[0]
            if target:
                assert (document.parent / target).resolve().is_file(), f"Broken local link in {document}: {link}"


def test_release_runbook_keeps_scope_and_database_recovery_blocked():
    runbook = (PROJECT_ROOT / "docs/evaluation/release_runbook.md").read_text(encoding="utf-8").casefold()

    assert "npm run test:e2e:roundtrip" in runbook
    assert "scripted" in runbook and "localhost" in runbook
    assert "không nhập" in runbook and "dữ liệu bệnh nhân" in runbook
    assert "không có quy trình sao lưu/khôi phục" in runbook
    assert "postgresql" in runbook and "blocked / not tested" in runbook
    assert "no-go" in runbook


def test_release_runbook_distinguishes_demo_hospital_trial_and_patient_use():
    runbook = (PROJECT_ROOT / "docs/evaluation/release_runbook.md").read_text(encoding="utf-8").casefold()

    assert "e2e kỹ thuật localhost với fixture tổng hợp | **go có giới hạn**" in runbook
    assert "chạy thử nội bộ tại bệnh viện với dữ liệu phi lâm sàng | **blocked**" in runbook
    assert "thử nghiệm lâm sàng | **blocked**" in runbook
    assert "chăm sóc hoặc quyết định trên bệnh nhân | **no-go**" in runbook


def test_release_runbook_has_scoped_recovery_for_failed_synthetic_demo():
    runbook = (PROJECT_ROOT / "docs/evaluation/release_runbook.md").read_text(encoding="utf-8").casefold()

    assert "quy trình phục hồi cho lần chạy demo bị lỗi" in runbook
    assert "server-ready.json" in runbook
    assert "không dừng process chỉ dựa vào số port" in runbook
    assert "giữ runtime lỗi làm evidence" in runbook
    assert "không khôi phục hoặc chép db tạm cũ" in runbook
    assert "không có quy trình sao lưu/khôi phục dữ liệu lâm sàng" in runbook


def test_readme_does_not_advertise_unverified_docker_launch():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8").casefold()

    assert "blocked / not verified" in readme
    assert "docker-compose up --build" not in readme
    assert "không dùng cấu hình này để triển khai" in readme


def test_clinical_validation_preparation_is_unapproved_and_does_not_invent_thresholds():
    protocol = (PROJECT_ROOT / "docs/evaluation/clinical-validation-preparation.md").read_text(encoding="utf-8").casefold()

    assert "draft — blocked" in protocol
    assert "không được dùng để tuyển ca" in protocol
    assert "patient-level independence" in protocol
    assert "tbd — không tự đặt" in protocol
    assert "không dùng dữ liệu tổng hợp làm bằng chứng xác thực lâm sàng" in protocol
    assert "không phải" in protocol and "protocol được phê duyệt" in protocol
    assert "độc lập" in protocol and "sai lệch" in protocol
    assert "https://www.imdrf.org/documents/software-medical-device-samd-clinical-evaluation" in protocol
    assert "https://www.nature.com/articles/s41591-025-03953-8" in protocol
    assert "https://jamanetwork.com/journals/jama/fullarticle/2833408" in protocol


def test_clinical_validation_preparation_preserves_patient_level_and_case_selection_gates():
    protocol = (PROJECT_ROOT / "docs/evaluation/clinical-validation-preparation.md").read_text(encoding="utf-8").casefold()

    assert "tiêu chí đưa vào/loại ra" in protocol
    assert "sampling frame" in protocol
    assert "không tạo patient id giả" in protocol
    assert "patient-level independence" in protocol
    assert "chưa được xác minh" in protocol
    assert "chỉ image-level split" in protocol
    assert "không đưa ra claim patient-level" in protocol
    assert "dữ liệu nghiên cứu không được chứa định danh trực tiếp trong repository" in protocol


def test_clinical_validation_preparation_requires_independent_reference_and_discrepancy_records():
    protocol = (PROJECT_ROOT / "docs/evaluation/clinical-validation-preparation.md").read_text(encoding="utf-8").casefold()

    assert "reference standard" in protocol
    assert "lượt đọc độc lập" in protocol
    assert "làm mù" in protocol
    assert "adjudication" in protocol
    assert "mẫu ghi nhận sai lệch" in protocol
    assert "mẫu ghi nhận bất đồng giữa người đọc trước phân xử" in protocol
    assert "reader a independent result" in protocol
    assert "reader b independent result" in protocol
    assert "không sửa hoặc ghi đè đánh giá ban đầu" in protocol
    assert "kết quả reference sau phân xử (trường riêng; không thay reader a/b)" in protocol
    assert "root cause" in protocol
    assert "không ghi tên, ngày sinh, pid nguồn" in protocol


def test_clinical_validation_preparation_keeps_acceptance_and_approvals_blocked():
    protocol = (PROJECT_ROOT / "docs/evaluation/clinical-validation-preparation.md").read_text(encoding="utf-8").casefold()

    assert "acceptance criteria" in protocol
    assert "tbd — không tự đặt" in protocol
    assert "hội đồng đạo đức" in protocol
    assert "đầu mối pháp quy" in protocol
    assert "data custodian" in protocol
    assert "không còn tbd" in protocol
    assert "blocked — chưa được phê duyệt, không bắt đầu cohort lâm sàng" in protocol
    assert "không dùng dữ liệu tổng hợp làm bằng chứng xác thực lâm sàng" in protocol


def test_audit_protocol_snapshot_points_to_the_canonical_preparation_worksheet():
    snapshot = PROJECT_ROOT / "artifacts/audit_remediation_2026_10_28/clinical-validation-protocol-draft.md"
    text = snapshot.read_text(encoding="utf-8")
    link = "../../docs/evaluation/clinical-validation-preparation.md"

    assert link in text
    assert (snapshot.parent / link).resolve().is_file()
