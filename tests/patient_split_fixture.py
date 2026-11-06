"""Build temporary source-bound patient split fixtures for validator tests."""

import csv
import hashlib
import json
from pathlib import Path


def attach_source_identity_evidence(split_dir: Path) -> None:
    split_dir = Path(split_dir)
    source_rows = []
    for split in ("train", "val", "test"):
        with (split_dir / f"{split}.csv").open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                source_rows.append({
                    "case_id": row.get("case_id", ""),
                    "patient_id": row.get("patient_id", ""),
                    "split": split.upper(),
                    "image_path": row.get("image_path", ""),
                    "mask_path": row.get("mask_path", ""),
                })

    metadata_path = split_dir / "source_metadata.csv"
    with metadata_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "patient_id", "split", "image_path", "mask_path"))
        writer.writeheader()
        writer.writerows(source_rows)
    metadata_hash = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    identity_path = split_dir / "identity_manifest.json"
    identity_path.write_text(json.dumps({
        "source_patient_identity_verified": True,
        "patient_ids_verified": True,
        "identity_level": "patient_verified",
        "identity_source": "synthetic test fixture",
        "identity_evidence_reference": "synthetic test fixture; not clinical evidence",
        "metadata_sha256": metadata_hash,
    }), encoding="utf-8")

    manifest_path = split_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "source_metadata_path": str(metadata_path.resolve()),
        "input_metadata_sha256": metadata_hash,
        "identity_manifest_path": str(identity_path.resolve()),
        "identity_manifest_sha256": hashlib.sha256(identity_path.read_bytes()).hexdigest(),
    })
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
