"""Regression check for the frozen index after source directories moved."""

import csv
import hashlib
import json

import cv2
import numpy as np
import pytest

from scripts import audit_milestone3_evidence as audit


def _csv(path, fields, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


@pytest.mark.parametrize("source", ["2d", "3d"])
def test_data_audit_resolves_relocated_image_mask_and_source_copy(tmp_path, monkeypatch, source):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    split = tmp_path / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    monkeypatch.setattr(audit, "SPLIT", split)

    image = tmp_path / f"dataset/{source}/images/one.JPG"
    mask_name = "one_binary.PNG" if source == "2d" else "one.PNG"
    mask = tmp_path / f"dataset/{source}/masks" / mask_name
    image.parent.mkdir(parents=True)
    mask.parent.mkdir(parents=True)
    image.write_bytes(cv2.imencode(".jpg", np.full((8, 8), 120, dtype=np.uint8))[1].tobytes())
    target = np.zeros((8, 8), dtype=np.uint8)
    target[2:6, 2:6] = 255
    mask.write_bytes(cv2.imencode(".png", target)[1].tobytes())
    image_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    mask_hash = hashlib.sha256(mask.read_bytes()).hexdigest()

    _csv(
        tmp_path / "dataset/index.csv",
        ("sample_id", "split", "image_path", "mask_path", "image_sha256", "source_target_paths"),
        [{
            "sample_id": image_hash,
            "split": "train",
            "image_path": f"dataset/Vinmec/Vinmec_{source}/images/one.JPG",
            "mask_path": f"dataset/Vinmec/Vinmec_{source}/annotations/one_binary.PNG",
            "image_sha256": image_hash,
            "source_target_paths": (
                "dataset/Vinmec_2D/train/train_label/label/one_binary.PNG"
                if source == "2d" else "dataset/Vinmec/Vinmec_3d/annotations/one_binary.PNG"
            ),
        }],
    )
    for name in ("train", "val", "test"):
        _csv(split / f"{name}.csv", ("image_sha256",), [{"image_sha256": image_hash}] if name == "train" else [])
        _csv(tmp_path / "ai_training/splits" / f"{name}.csv", ("is_empty_mask", "image_path", "mask_path", "case_id"), [])
    _csv(
        tmp_path / "evaluation/milestone_3_audit_2026-10-06/verified_data/mask_provenance.csv",
        ("sample_id", "mask_sha256"),
        [{"sample_id": image_hash, "mask_sha256": mask_hash}] if source == "2d" else [],
    )
    _csv(
        tmp_path / "reports/dataset_deduplication_report.csv",
        ("source_dataset", "image_hash", "mask_hash"),
        [{"source_dataset": "Vinmec_CEUS", "image_hash": image_hash, "mask_hash": mask_hash}]
        if source == "3d" else [],
    )

    output = tmp_path / "audit"
    output.mkdir()
    audit.data_audit(output)

    result = json.loads((output / "dataset_audit.json").read_text(encoding="utf-8"))
    assert result["verified_readable_pairs"] == 1
    assert result["frozen_mask_sha_verified"] == 1
    assert result["errors"] == []
    assert result["missing_source_path_references"] == 0
    assert result["image_content_overlap"] == {"train/val": 0, "train/test": 0, "val/test": 0}

    mask.write_bytes(cv2.imencode(".png", np.zeros((8, 8), dtype=np.uint8))[1].tobytes())
    changed_output = tmp_path / "changed_audit"
    changed_output.mkdir()
    audit.data_audit(changed_output)
    changed = json.loads((changed_output / "dataset_audit.json").read_text(encoding="utf-8"))
    assert changed["verified_readable_pairs"] == 0
    assert "Frozen mask SHA" in changed["errors"][0]["error"]
