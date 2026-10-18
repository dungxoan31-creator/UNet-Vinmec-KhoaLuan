"""Evaluation Protocol Loader and Input Auditor for Milestone 3."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    from backend.core.dataset_paths import resolve_dataset_path
except ImportError:
    def resolve_dataset_path(root: Path, recorded: str) -> Path:
        relative = recorded.replace("\\", "/")
        original = root / relative
        if original.is_file():
            return original
        parts = relative.split("/")
        if len(parts) < 4 or parts[0] != "dataset":
            return original
        source = "/".join(parts[1:-1])
        name = parts[-1]
        if source in {"Vinmec/Vinmec_2d/images", "Vinmec_2D/train/train_image", "Vinmec_2D/test/image"}:
            return root / "dataset/2d/images" / name
        if source in {"Vinmec/Vinmec_2d/annotations", "Vinmec_2D/train/train_label/label", "Vinmec_2D/test/label/black_write"}:
            return root / "dataset/2d/masks" / name
        if source == "Vinmec/Vinmec_3d/images":
            return root / "dataset/3d/images" / name
        if source == "Vinmec/Vinmec_3d/annotations":
            return root / "dataset/3d/masks" / (name.removesuffix("_binary.PNG") + ".PNG")
        return original


def load_protocol(path: Path) -> dict[str, Any]:
    """Load and validate the frozen protocol JSON."""
    if not path.is_file():
        raise FileNotFoundError(f"Protocol file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    required_keys = ["schema_version", "protocol_id", "run_kinds", "model", "preprocess", "inference"]
    for k in required_keys:
        if k not in data:
            raise ValueError(f"Protocol missing required key: {k}")

    return data


def load_cases(root: Path, manifest: Path) -> list[dict[str, Any]]:
    """Load and validate normalized manifest v1 CSV rows."""
    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest file not found: {manifest}")

    cases = []
    seen_sample_ids = set()

    with open(manifest, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required_cols = {"sample_id", "image_path", "mask_path"}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"Manifest missing required columns: {required_cols - set(reader.fieldnames or [])}")

        for row_idx, row in enumerate(reader, start=2):
            sample_id = (row.get("sample_id") or "").strip()
            if not sample_id:
                raise ValueError(f"Row {row_idx}: sample_id cannot be empty")
            if sample_id in seen_sample_ids:
                raise ValueError(f"Row {row_idx}: duplicate sample_id '{sample_id}'")
            seen_sample_ids.add(sample_id)
            cases.append(row)

    return cases


def normalize_reference(mask: np.ndarray) -> np.ndarray:
    """Validate 2D mask and normalize values in {0, 255} to {0, 1}."""
    if mask.ndim != 2:
        raise ValueError(f"Reference mask must be 2D, got shape {mask.shape}")
    if mask.size == 0:
        raise ValueError("Reference mask has size 0")

    unique_vals = set(np.unique(mask).tolist())
    allowed = {0, 1, 255}
    if not unique_vals.issubset(allowed):
        raise ValueError(f"Reference mask contains invalid values: {unique_vals - allowed}")

    out = mask.copy()
    if 255 in unique_vals:
        out[out == 255] = 1
    return out.astype(np.uint8)


def _check_safe_relative_path(root: Path, rel_path_str: str) -> Path | None:
    """Ensure a relative path does not escape root."""
    try:
        resolved = (root / rel_path_str).resolve()
        resolved.relative_to(root.resolve())
        return resolved
    except (ValueError, RuntimeError):
        return None


def audit_inputs(root: Path, cases: list[dict[str, Any]], protocol: dict[str, Any], run_kind: str) -> dict[str, Any]:
    """Audit dataset inputs, geometry, hashes, and data independence gate."""
    allowed_runs = protocol.get("run_kinds", [])
    if run_kind not in allowed_runs:
        raise ValueError(f"Unknown run_kind '{run_kind}'. Allowed: {allowed_runs}")

    errors: list[str] = []
    failures: list[dict[str, Any]] = []
    status = "READY"

    counts = {
        "total": len(cases),
        "valid": 0,
        "failed": 0
    }

    patient_independence = {
        "run_kind": run_kind,
        "verified": False,
        "patient_count": 0,
        "notes": []
    }

    label_provenance = {
        "verified": False,
        "evidence_sources": []
    }

    seen_patients = set()
    train_val_patients = set()

    # Pre-check for independent_test
    if run_kind == "independent_test":
        for case in cases:
            dev_evidence = case.get("development_history_evidence")
            if dev_evidence and dev_evidence.strip():
                dev_path = _check_safe_relative_path(root, dev_evidence.strip())
                if dev_path and dev_path.is_file():
                    try:
                        content = json.loads(dev_path.read_text(encoding="utf-8"))
                        if isinstance(content, dict):
                            for key in ["train_patients", "val_patients", "development_patients"]:
                                if key in content and isinstance(content[key], list):
                                    train_val_patients.update(content[key])
                    except Exception as e:
                        errors.append(f"Could not parse development history evidence {dev_path}: {e}")

    for idx, case in enumerate(cases):
        sample_id = case.get("sample_id", f"sample_{idx}")
        image_path_str = case.get("image_path", "")
        mask_path_str = case.get("mask_path", "")
        patient_id = (case.get("patient_id") or "").strip()

        case_errors = []

        if run_kind == "independent_test":
            if not patient_id:
                case_errors.append(f"Sample '{sample_id}' has empty patient_id; required for independent_test")
            else:
                seen_patients.add(patient_id)
                if patient_id in train_val_patients:
                    case_errors.append(f"Sample '{sample_id}' patient_id '{patient_id}' overlaps with development history")

            for ev_key in ["identity_evidence", "label_evidence", "development_history_evidence"]:
                ev_val = (case.get(ev_key) or "").strip()
                if not ev_val:
                    case_errors.append(f"Sample '{sample_id}' missing required '{ev_key}'")
                else:
                    safe_path = _check_safe_relative_path(root, ev_val)
                    if not safe_path:
                        case_errors.append(f"Sample '{sample_id}' {ev_key} '{ev_val}' escapes root path")
                    elif not safe_path.is_file():
                        case_errors.append(f"Sample '{sample_id}' {ev_key} file not found: {ev_val}")

        # Resolve image and mask paths
        img_resolved = resolve_dataset_path(root, image_path_str)
        mask_resolved = resolve_dataset_path(root, mask_path_str)

        if not img_resolved.is_file():
            case_errors.append(f"Sample '{sample_id}': Image file not found: {img_resolved}")
        if not mask_resolved.is_file():
            case_errors.append(f"Sample '{sample_id}': Mask file not found: {mask_resolved}")

        if not case_errors:
            # Check SHA256 if recorded
            img_bytes = img_resolved.read_bytes()
            mask_bytes = mask_resolved.read_bytes()

            rec_img_sha = (case.get("image_sha256") or "").strip().lower()
            rec_mask_sha = (case.get("mask_sha256") or "").strip().lower()

            if rec_img_sha:
                calc_img_sha = hashlib.sha256(img_bytes).hexdigest().lower()
                if calc_img_sha != rec_img_sha:
                    case_errors.append(f"Sample '{sample_id}': Image SHA256 mismatch (expected {rec_img_sha}, got {calc_img_sha})")

            if rec_mask_sha:
                calc_mask_sha = hashlib.sha256(mask_bytes).hexdigest().lower()
                if calc_mask_sha != rec_mask_sha:
                    case_errors.append(f"Sample '{sample_id}': Mask SHA256 mismatch (expected {rec_mask_sha}, got {calc_mask_sha})")

            # Decode image and mask
            img_arr = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
            mask_arr = cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)

            if img_arr is None:
                case_errors.append(f"Sample '{sample_id}': Could not decode image as grayscale")
            if mask_arr is None:
                case_errors.append(f"Sample '{sample_id}': Could not decode mask as grayscale")

            if img_arr is not None and mask_arr is not None:
                if img_arr.shape != mask_arr.shape:
                    case_errors.append(f"Sample '{sample_id}': Shape mismatch (image {img_arr.shape} vs mask {mask_arr.shape})")
                try:
                    normalize_reference(mask_arr)
                except ValueError as ve:
                    case_errors.append(f"Sample '{sample_id}': Invalid mask values: {ve}")

        if case_errors:
            counts["failed"] += 1
            errors.extend(case_errors)
            failures.append({
                "sample_id": sample_id,
                "errors": "; ".join(case_errors)
            })
        else:
            counts["valid"] += 1

    if run_kind == "independent_test":
        patient_independence["patient_count"] = len(seen_patients)
        if any("patient_id" in err or "evidence" in err or "escape" in err or "overlap" in err for err in errors):
            status = "BLOCKED"
        elif errors:
            status = "FAILED"
        else:
            status = "READY"
            patient_independence["verified"] = True
    else:
        if errors:
            status = "FAILED"
        else:
            status = "READY"

    return {
        "status": status,
        "run_kind": run_kind,
        "counts": counts,
        "errors": errors,
        "failures": failures,
        "patient_independence": patient_independence,
        "label_provenance": label_provenance,
        "protected_hashes": {
            "protocol_sha256": hashlib.sha256(json.dumps(protocol, sort_keys=True).encode("utf-8")).hexdigest()
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Audit evaluation input data and protocol gates.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Repo root directory")
    parser.add_argument("--protocol", type=Path, required=True, help="Path to protocol JSON")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to manifest CSV")
    parser.add_argument("--run-kind", type=str, required=True, choices=["validation_dry_run", "retrospective_test_replay", "independent_test"])
    parser.add_argument("--output", type=Path, required=True, help="Directory to write audit.json and failures.csv")

    args = parser.parse_args()
    root = args.root.resolve()
    protocol = load_protocol(args.protocol)
    cases = load_cases(root, args.manifest)

    audit = audit_inputs(root, cases, protocol, args.run_kind)

    args.output.mkdir(parents=True, exist_ok=True)
    with open(args.output / "audit.json", "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)

    with open(args.output / "failures.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["sample_id", "errors"])
        writer.writeheader()
        writer.writerows(audit["failures"])

    print(f"Audit Status: {audit['status']} (Valid: {audit['counts']['valid']}, Failed: {audit['counts']['failed']})")
    if audit["status"] != "READY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
