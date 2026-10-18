"""Check file bindings in a supplied mask-approval ledger.

This is a technical audit only. A matching document hash cannot establish the
reviewer's identity, authority, or the clinical meaning of an empty mask.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from backend.core.dataset_paths import resolve_dataset_path

REQUIRED = (
    "sample_id", "image_sha256", "mask_sha256", "approval_document_path",
    "approval_document_sha256", "reviewer_id", "approved_at", "decision",
)


def _hash_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_approval_manifest(root: Path, index_path: Path, manifest_path: Path) -> dict:
    """Return per-row technical status; clinical approval stays UNKNOWN."""
    root = Path(root)
    with Path(index_path).open(encoding="utf-8-sig", newline="") as stream:
        index = {row["sample_id"]: row for row in csv.DictReader(stream)}
    with Path(manifest_path).open(encoding="utf-8-sig", newline="") as stream:
        ledger = csv.DictReader(stream)
        if not set(REQUIRED).issubset(ledger.fieldnames or []):
            raise ValueError("Approval ledger lacks required columns: " + ", ".join(REQUIRED))
        evidence_rows = list(ledger)

    checked = []
    seen = set()
    for evidence in evidence_rows:
        sample_id = evidence["sample_id"]
        record = index.get(sample_id)
        if not all(evidence.get(key, "").strip() for key in REQUIRED):
            status = "INCOMPLETE_EVIDENCE"
        elif sample_id in seen:
            status = "DUPLICATE_SAMPLE"
        elif record is None:
            status = "SAMPLE_NOT_IN_INDEX"
        elif evidence["image_sha256"].lower() != record["image_sha256"].lower():
            status = "IMAGE_HASH_MISMATCH"
        elif _hash_file(resolve_dataset_path(root, record["image_path"])) != evidence["image_sha256"].lower():
            status = "IMAGE_HASH_MISMATCH"
        elif _hash_file(resolve_dataset_path(root, record["mask_path"])) != evidence["mask_sha256"].lower():
            status = "MASK_HASH_MISMATCH"
        elif _hash_file(resolve_dataset_path(root, evidence["approval_document_path"])) != evidence["approval_document_sha256"].lower():
            status = "DOCUMENT_HASH_MISMATCH"
        else:
            status = "FILES_MATCH"
        seen.add(sample_id)
        checked.append({"sample_id": sample_id, "technical_status": status, "clinical_approval": "UNKNOWN"})

    return {
        "rows_checked": len(checked),
        "files_match_count": sum(row["technical_status"] == "FILES_MATCH" for row in checked),
        "official_ground_truth_count": 0,
        "rows": checked,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_approval_manifest(args.root, args.index, args.manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
