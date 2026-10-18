import csv
import hashlib

from scripts.audit_mask_approval_evidence import audit_approval_manifest


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_approval_audit_matches_files_without_claiming_clinical_signoff(tmp_path):
    image = tmp_path / "image.png"
    mask = tmp_path / "mask.png"
    document = tmp_path / "approval.pdf"
    image.write_bytes(b"image")
    mask.write_bytes(b"mask")
    document.write_bytes(b"document")
    index = tmp_path / "index.csv"
    _write_csv(index, ["sample_id", "image_path", "mask_path", "image_sha256"], [{
        "sample_id": "sample-1", "image_path": image.name, "mask_path": mask.name,
        "image_sha256": _sha(image),
    }])
    manifest = tmp_path / "approval.csv"
    row = {
        "sample_id": "sample-1", "image_sha256": _sha(image),
        "mask_sha256": _sha(mask), "approval_document_path": document.name,
        "approval_document_sha256": _sha(document), "reviewer_id": "reviewer-1",
        "approved_at": "2026-10-08", "decision": "APPROVED",
    }
    _write_csv(manifest, list(row), [row])

    result = audit_approval_manifest(tmp_path, index, manifest)
    assert result["rows"][0]["technical_status"] == "FILES_MATCH"
    assert result["rows"][0]["clinical_approval"] == "UNKNOWN"
    assert result["official_ground_truth_count"] == 0

    row["mask_sha256"] = "0" * 64
    _write_csv(manifest, list(row), [row])
    changed = audit_approval_manifest(tmp_path, index, manifest)
    assert changed["rows"][0]["technical_status"] == "MASK_HASH_MISMATCH"
