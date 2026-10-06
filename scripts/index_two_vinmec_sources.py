"""Export the two authorized sources as a versioned index without changing data or frozen splits."""

import hashlib
from collections import Counter
from datetime import UTC, datetime

from scripts.audit_milestone3_evidence import ROOT, SPLIT, readable, rows, sha, write_csv, write_json

OUTPUT = ROOT / "evaluation/milestone_3_audit_2026-10-06"


def main():
    frozen = {}
    for split in ("train", "val", "test"):
        for row in rows(SPLIT / f"{split}.csv"):
            frozen[row["image_sha256"]] = {**row, "split": split}
    records, errors, seen = [], [], set()
    for source in ("Vinmec_2d", "Vinmec_3d"):
        folder = ROOT / "dataset/Vinmec" / source
        for image in sorted((folder / "images").iterdir()):
            if not image.is_file():
                continue
            candidates = [
                p for p in (folder / "annotations").iterdir() if p.stem.lower() == image.stem.lower() + "_binary"
            ]
            if len(candidates) != 1:
                errors.append(
                    {
                        "image": image.relative_to(ROOT).as_posix(),
                        "error": f"expected one scoped binary target; found {len(candidates)}",
                    }
                )
                continue
            target = candidates[0]
            img, mask = readable(image), readable(target)
            if img is None or mask is None or img.shape != mask.shape:
                errors.append(
                    {
                        "image": image.relative_to(ROOT).as_posix(),
                        "error": "unreadable or mismatched image / target dimensions",
                    }
                )
                continue
            digest = sha(image)
            if digest in seen:
                errors.append(
                    {
                        "image": image.relative_to(ROOT).as_posix(),
                        "error": "duplicate image SHA in the two source folders",
                    }
                )
                continue
            seen.add(digest)
            evidence = frozen.get(digest)
            if evidence and (ROOT / evidence["mask_path"]).resolve() != target.resolve():
                raise ValueError("Target differs from frozen split; do not infer a new target")
            records.append(
                {
                    "sample_id": digest,
                    "dataset": source,
                    "patient_id": "",
                    "case_id": "",
                    "identity_level": "image_content_only; source_patient_case_unverified",
                    "image_path": image.relative_to(ROOT).as_posix(),
                    "annotation_path": target.relative_to(ROOT).as_posix(),
                    "label_path": target.relative_to(ROOT).as_posix(),
                    "mask_path": target.relative_to(ROOT).as_posix(),
                    "target_roles_note": "one binary annotation file serves as segmentation label and mask; not three independent labels",
                    "mask_sha256": sha(target),
                    "binary_mask_sha256": hashlib.sha256((mask > 0).tobytes()).hexdigest(),
                    "split": evidence["split"] if evidence else "excluded",
                    "status": "verified_mapping_supplied_reference" if evidence else "excluded_not_in_frozen_manifest",
                    "exclusion_reason": ""
                    if evidence
                    else "historical_manifest_excludes_35_fallback_associated_images; original_per_file_fallback_provenance_unavailable",
                    "clinical_ground_truth_approval": "not_verified",
                }
            )
    if set(frozen) - seen:
        raise ValueError("Some frozen samples are missing from the authorized sources")
    target = OUTPUT / "active_two_source_index.csv"
    if target.exists():
        raise FileExistsError("Versioned index already exists")
    write_csv(target, records)
    write_json(
        OUTPUT / "two_source_inventory.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "command": "python scripts/index_two_vinmec_sources.py",
            "owner_requested_scope": ["dataset/Vinmec/Vinmec_2d", "dataset/Vinmec/Vinmec_3d"],
            "counts": {
                source: dict(Counter(r["split"] for r in records if r["dataset"] == source))
                for source in ("Vinmec_2d", "Vinmec_3d")
            },
            "physical_images": len(records) + len(errors),
            "valid_frozen_samples": sum(r["split"] != "excluded" for r in records),
            "excluded": sum(r["split"] == "excluded" for r in records),
            "errors": errors,
            "index": target.relative_to(ROOT).as_posix(),
            "index_sha256": sha(target),
            "split_changed": False,
            "patient_level_independence": "not_verified",
            "clinical_mask_approval": "not_verified",
        },
    )
    print("records", len(records), "errors", len(errors))


if __name__ == "__main__":
    main()
