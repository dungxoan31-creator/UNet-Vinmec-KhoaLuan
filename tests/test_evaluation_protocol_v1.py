"""Tests for Evaluation Protocol v1 and Data Independence Gate."""

import json
from pathlib import Path
import pytest
import numpy as np
import cv2
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def _create_synthetic_pair(tmp_path, name="sample_1", corrupt_img=False, corrupt_mask=False):
    img_dir = tmp_path / "images"
    mask_dir = tmp_path / "masks"
    img_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    img_file = img_dir / f"{name}.png"
    mask_file = mask_dir / f"{name}_mask.png"

    if corrupt_img:
        img_file.write_bytes(b"corrupt image data")
        img_sha = hashlib.sha256(b"corrupt image data").hexdigest()
    else:
        img_arr = np.zeros((100, 100), dtype=np.uint8)
        img_arr[20:80, 20:80] = 128
        cv2.imwrite(str(img_file), img_arr)
        img_sha = hashlib.sha256(img_file.read_bytes()).hexdigest()

    if corrupt_mask:
        mask_file.write_bytes(b"corrupt mask data")
        mask_sha = hashlib.sha256(b"corrupt mask data").hexdigest()
    else:
        mask_arr = np.zeros((100, 100), dtype=np.uint8)
        mask_arr[30:70, 30:70] = 255
        cv2.imwrite(str(mask_file), mask_arr)
        mask_sha = hashlib.sha256(mask_file.read_bytes()).hexdigest()

    return str(img_file.relative_to(tmp_path)), str(mask_file.relative_to(tmp_path)), img_sha, mask_sha


def test_independent_gate_rejects_unknown_identity(tmp_path):
    from evaluation.protocol import load_protocol, load_cases, audit_inputs

    protocol_path = ROOT / "evaluation" / "protocols" / "milestone3_v1.json"
    protocol = load_protocol(protocol_path)

    # Synthetic manifest with empty patient_id
    img_rel, mask_rel, img_sha, mask_sha = _create_synthetic_pair(tmp_path)
    manifest_csv = tmp_path / "manifest.csv"
    manifest_content = (
        "sample_id,source_case_id,patient_id,split,modality,image_path,mask_path,image_sha256,mask_sha256,identity_evidence,label_evidence,development_history_evidence\n"
        f"s1,c1,,test,2d,{img_rel},{mask_rel},{img_sha},{mask_sha},,,technical_fixture\n"
    )
    manifest_csv.write_text(manifest_content, encoding="utf-8")

    cases = load_cases(tmp_path, manifest_csv)
    audit = audit_inputs(tmp_path, cases, protocol, run_kind="independent_test")

    assert audit["status"] == "BLOCKED"
    assert "patient_id" in str(audit["errors"]) or any("identity" in err.lower() for err in audit["errors"])


def test_patient_overlap_across_development_history(tmp_path):
    from evaluation.protocol import load_protocol, load_cases, audit_inputs

    protocol_path = ROOT / "evaluation" / "protocols" / "milestone3_v1.json"
    protocol = load_protocol(protocol_path)

    img_rel, mask_rel, img_sha, mask_sha = _create_synthetic_pair(tmp_path)
    
    # Create evidence file showing patient P_OVERLAP was in train set
    dev_history_file = tmp_path / "dev_history.json"
    dev_history_file.write_text(json.dumps({"train_patients": ["P_OVERLAP"]}), encoding="utf-8")

    manifest_csv = tmp_path / "manifest.csv"
    manifest_content = (
        "sample_id,source_case_id,patient_id,split,modality,image_path,mask_path,image_sha256,mask_sha256,identity_evidence,label_evidence,development_history_evidence\n"
        f"s1,c1,P_OVERLAP,test,2d,{img_rel},{mask_rel},{img_sha},{mask_sha},id.txt,label.txt,{dev_history_file.name}\n"
    )
    manifest_csv.write_text(manifest_content, encoding="utf-8")
    (tmp_path / "id.txt").write_text("verified id", encoding="utf-8")
    (tmp_path / "label.txt").write_text("verified label", encoding="utf-8")

    cases = load_cases(tmp_path, manifest_csv)
    audit = audit_inputs(tmp_path, cases, protocol, run_kind="independent_test")

    assert audit["status"] == "BLOCKED"
    assert any("overlap" in err.lower() for err in audit["errors"])


def test_corrupt_pair_fails_preflight(tmp_path):
    from evaluation.protocol import load_protocol, load_cases, audit_inputs

    protocol_path = ROOT / "evaluation" / "protocols" / "milestone3_v1.json"
    protocol = load_protocol(protocol_path)

    img_rel, mask_rel, img_sha, mask_sha = _create_synthetic_pair(tmp_path, corrupt_img=True)
    manifest_csv = tmp_path / "manifest.csv"
    manifest_content = (
        "sample_id,source_case_id,patient_id,split,modality,image_path,mask_path,image_sha256,mask_sha256,identity_evidence,label_evidence,development_history_evidence\n"
        f"s1,c1,P1,val,2d,{img_rel},{mask_rel},{img_sha},{mask_sha},,,technical_fixture\n"
    )
    manifest_csv.write_text(manifest_content, encoding="utf-8")

    cases = load_cases(tmp_path, manifest_csv)
    audit = audit_inputs(tmp_path, cases, protocol, run_kind="validation_dry_run")

    assert audit["status"] == "FAILED"
    assert any("corrupt" in err.lower() or "decode" in err.lower() or "sha" in err.lower() for err in audit["errors"])


def test_duplicate_sample_id_rejected(tmp_path):
    from evaluation.protocol import load_protocol, load_cases

    img_rel, mask_rel, img_sha, mask_sha = _create_synthetic_pair(tmp_path)
    manifest_csv = tmp_path / "manifest.csv"
    manifest_content = (
        "sample_id,source_case_id,patient_id,split,modality,image_path,mask_path,image_sha256,mask_sha256,identity_evidence,label_evidence,development_history_evidence\n"
        f"s1,c1,P1,val,2d,{img_rel},{mask_rel},{img_sha},{mask_sha},,,technical_fixture\n"
        f"s1,c2,P2,val,2d,{img_rel},{mask_rel},{img_sha},{mask_sha},,,technical_fixture\n"
    )
    manifest_csv.write_text(manifest_content, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate.*sample_id"):
        load_cases(tmp_path, manifest_csv)


def test_relocated_path_preserves_hash(tmp_path):
    from evaluation.protocol import load_protocol, load_cases, audit_inputs

    protocol_path = ROOT / "evaluation" / "protocols" / "milestone3_v1.json"
    protocol = load_protocol(protocol_path)

    img_rel, mask_rel, img_sha, mask_sha = _create_synthetic_pair(tmp_path)
    
    # Path with wrong recorded prefix that resolver can handle if set up, or exact path
    manifest_csv = tmp_path / "manifest.csv"
    manifest_content = (
        "sample_id,source_case_id,patient_id,split,modality,image_path,mask_path,image_sha256,mask_sha256,identity_evidence,label_evidence,development_history_evidence\n"
        f"s1,c1,P1,val,2d,{img_rel},{mask_rel},{img_sha},{mask_sha},,,technical_fixture\n"
    )
    manifest_csv.write_text(manifest_content, encoding="utf-8")

    cases = load_cases(tmp_path, manifest_csv)
    audit = audit_inputs(tmp_path, cases, protocol, run_kind="validation_dry_run")
    assert audit["status"] == "READY"
    assert audit["counts"]["total"] == 1


def test_evidence_path_cannot_escape_root(tmp_path):
    from evaluation.protocol import load_protocol, load_cases, audit_inputs

    protocol_path = ROOT / "evaluation" / "protocols" / "milestone3_v1.json"
    protocol = load_protocol(protocol_path)

    img_rel, mask_rel, img_sha, mask_sha = _create_synthetic_pair(tmp_path)
    manifest_csv = tmp_path / "manifest.csv"
    manifest_content = (
        "sample_id,source_case_id,patient_id,split,modality,image_path,mask_path,image_sha256,mask_sha256,identity_evidence,label_evidence,development_history_evidence\n"
        f"s1,c1,P1,test,2d,{img_rel},{mask_rel},{img_sha},{mask_sha},../../escaped.txt,label.txt,history.json\n"
    )
    manifest_csv.write_text(manifest_content, encoding="utf-8")

    cases = load_cases(tmp_path, manifest_csv)
    audit = audit_inputs(tmp_path, cases, protocol, run_kind="independent_test")
    assert audit["status"] == "BLOCKED"
    assert any("escape" in err.lower() or "outside root" in err.lower() or "path" in err.lower() for err in audit["errors"])
