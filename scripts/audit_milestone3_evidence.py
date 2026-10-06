"""Read-only evidence inventory and data provenance audit; writes only to a new output directory."""

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from docx import Document
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8", errors="replace").strip()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path, data):
    if not data:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def readable(path):
    if not path.is_file():
        return None
    array = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
    if array is None:
        raise ValueError(f"OpenCV cannot decode {path}")
    with Image.open(path) as pil:
        pil.load()
        if pil.size != (array.shape[1], array.shape[0]):
            raise ValueError(f"Pillow / OpenCV dimensions disagree: {path}")
    return array


def inventory(output):
    tracked = set(git("ls-files").splitlines())
    records = []
    for area in (
        "checkpoints",
        "evaluation",
        "ai_training/splits",
        "metadata",
        "docs",
        "reports",
        "frontend",
        "backend",
        "scripts",
        "tests",
    ):
        for path in sorted((ROOT / area).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or output in path.parents:
                continue
            relative = path.relative_to(ROOT).as_posix()
            records.append(
                {
                    "path": relative,
                    "artifact_type": area,
                    "sha256": sha(path),
                    "bytes": path.stat().st_size,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                    "git_status": "tracked" if relative in tracked else "untracked_or_ignored",
                    "evidence_eligibility": "requires_provenance_and_scope_review",
                    "related_artifact": "",
                }
            )
    for name in ("README.md", "MODEL_CARD.md", "TECH_STACK.md", "dataset/index.csv"):
        path = ROOT / name
        records.append(
            {
                "path": name,
                "artifact_type": "documentation_or_index",
                "sha256": sha(path),
                "bytes": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                "git_status": "tracked" if name in tracked else "untracked_or_ignored",
                "evidence_eligibility": "requires_provenance_and_scope_review",
                "related_artifact": "",
            }
        )
    write_csv(output / "evidence_inventory.csv", records)
    by_hash = defaultdict(list)
    for record in records:
        by_hash[record["sha256"]].append(record["path"])
    deleted = []
    for line in git("diff", "--name-status", "HEAD~1", "HEAD").splitlines():
        status, *paths = line.split("\t")
        if status != "D":
            continue
        path = paths[0]
        blob = subprocess.check_output(["git", "show", f"HEAD~1:{path}"], cwd=ROOT)
        digest = hashlib.sha256(blob).hexdigest()
        copies = by_hash[digest]
        deleted.append(
            {
                "path": path,
                "git_change": "deleted_in_previous_committed_change",
                "current_exists": (ROOT / path).is_file(),
                "previous_sha256": digest,
                "identical_current_paths": ";".join(copies),
                "retention": "recoverable_from_git; no_restore_performed",
                "report_risk": "path_references_may_be_broken; check_deleted_reference_scan.txt",
            }
        )
    write_csv(output / "committed_deletions.csv", deleted)
    search_files = [r["path"] for r in records if Path(r["path"]).suffix in {".md", ".json", ".py", ".js"}]
    references = []
    for record in deleted:
        for filename in search_files:
            if record["path"] in (ROOT / filename).read_text(encoding="utf-8", errors="replace"):
                references.append(f"{filename} -> {record['path']}")
    (output / "deleted_reference_scan.txt").write_text("\n".join(references) + "\n", encoding="utf-8")
    docs = []
    for path in (ROOT / "docs/reports").glob("*.docx"):
        document = Document(path)
        text = "\n".join(
            [p.text for p in document.paragraphs]
            + [c.text for t in document.tables for row in t.rows for c in row.cells]
        )
        docs.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                "core_modified": str(document.core_properties.modified),
                "paragraphs": len(document.paragraphs),
                "tables": len(document.tables),
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "text_excerpt": text[:650],
            }
        )
        (output / f"{path.stem}_extracted.txt").write_text(text, encoding="utf-8")
    write_json(output / "docx_versions.json", docs)
    write_json(
        output / "inventory_summary.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "command": "python scripts/audit_milestone3_evidence.py --output " + output.relative_to(ROOT).as_posix(),
            "head": git("rev-parse", "HEAD"),
            "initial_git_status": git("status", "--porcelain=v1"),
            "history": git("log", "-12", "--format=%H %aI %s"),
            "remote": git("remote", "-v"),
            "artifact_count": len(records),
            "deleted_in_latest_commit": len(deleted),
            "deleted_with_identical_copy": sum(bool(r["identical_current_paths"]) for r in deleted),
            "references_to_deleted_files": references,
        },
    )
    return records


def data_audit(output):
    canonical = rows(ROOT / "dataset/index.csv")
    split_rows = {s: rows(SPLIT / f"{s}.csv") for s in ("train", "val", "test")}
    hashes = {s: {r["image_sha256"] for r in data} for s, data in split_rows.items()}
    overlaps = {
        f"{a}/{b}": len(hashes[a] & hashes[b]) for a, b in (("train", "val"), ("train", "test"), ("val", "test"))
    }
    masks, errors, missing_sources = [], [], []
    for row in canonical:
        image, mask = ROOT / row["image_path"], ROOT / row["mask_path"]
        try:
            img, target = readable(image), readable(mask)
            if img is None or target is None:
                raise ValueError("Image or reference mask missing")
            if img.shape != target.shape:
                raise ValueError("Image / target spatial dimensions differ")
            if sha(image) != row["image_sha256"]:
                raise ValueError("Image SHA differs from canonical index")
            binary = target > 0
            source_masks = row["source_target_paths"].split(";")
            missing = []
            for source in source_masks:
                copy = readable(ROOT / source)
                if copy is None:
                    missing.append(source)
                    missing_sources.append(
                        {
                            "sample_id": row["sample_id"],
                            "missing_source_path": source,
                            "canonical_mask_path": row["mask_path"],
                            "status": "missing_not_a_pixel_disagreement",
                        }
                    )
                elif copy.shape != target.shape or not np.array_equal(copy > 0, binary):
                    raise ValueError(f"Source target disagreement: {source}")
            masks.append(
                {
                    "sample_id": row["sample_id"],
                    "split": row["split"],
                    "image_path": row["image_path"],
                    "mask_path": row["mask_path"],
                    "image_sha256": row["image_sha256"],
                    "mask_sha256": sha(mask),
                    "source_target_paths": row["source_target_paths"],
                    "foreground_pixels": int(binary.sum()),
                    "mapping_status": "canonical_and_existing_duplicate_targets_verified",
                    "missing_source_paths": ";".join(missing),
                    "clinical_approval": "not_verified; named_expert_or_provider_label_approval_missing",
                }
            )
        except (OSError, ValueError) as exc:
            errors.append({"sample_id": row["sample_id"], "error": str(exc)})
    write_csv(output / "mask_provenance.csv", masks)
    write_csv(output / "missing_source_paths.csv", missing_sources)
    fallback = []
    for split in ("train", "val", "test"):
        for row in rows(ROOT / f"ai_training/splits/{split}.csv"):
            if row.get("is_empty_mask", "").lower() != "true":
                continue
            image, mask = ROOT / row["image_path"], ROOT / row["mask_path"]
            arr = readable(mask)
            image_hash = sha(image) if image.is_file() else None
            fallback.append(
                {
                    "case_id": row["case_id"],
                    "split": split,
                    "image_path": row["image_path"],
                    "mask_path": row["mask_path"],
                    "exists": mask.is_file(),
                    "mask_sha256": sha(mask) if mask.is_file() else "",
                    "shape": str(arr.shape) if arr is not None else "",
                    "foreground_pixels": int((arr > 0).sum()) if arr is not None else "",
                    "image_sha256": image_hash,
                    "in_unified_index": image_hash in {r["image_sha256"] for r in canonical},
                    "classification": "pipeline_fallback_artifact; not_clinical_ground_truth_or_negative_case",
                    "historical_generator": "scripts/generate_m1_empty_masks.py; original_per_file_provenance_not_found",
                }
            )
    write_csv(output / "fallback_mask_provenance.csv", fallback)
    write_json(
        output / "dataset_audit.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "counts": {s: len(r) for s, r in split_rows.items()},
            "canonical_samples": len(canonical),
            "verified_readable_pairs": len(masks),
            "errors": errors,
            "missing_source_path_references": len(missing_sources),
            "samples_with_missing_source_references": len({r["sample_id"] for r in missing_sources}),
            "image_content_overlap": overlaps,
            "identity_classification": "C: image/file identifiers; historical anonymous groups B",
            "patient_level_independence": "not_verified",
            "missing_evidence": "provider-confirmed image-to-patient/case mapping and expert label approval",
            "original_fallback_provenance_exists": (
                ROOT / "dataset/vinmec_ovarian/empty_masks/PROVENANCE.json"
            ).is_file(),
            "fallback_count": len(fallback),
            "fallback_splits": dict(Counter(r["split"] for r in fallback)),
            "fallback_in_unified_index": sum(r["in_unified_index"] for r in fallback),
            "empty_reference_masks_in_unified": sum(r["foreground_pixels"] == 0 for r in masks),
            "protected_hashes": {p.relative_to(ROOT).as_posix(): sha(p) for p in list(SPLIT.glob("*")) if p.is_file()},
        },
    )


def recover_history(output):
    recovered = []
    for record in rows(output / "committed_deletions.csv"):
        if record["identical_current_paths"] or Path(record["path"]).suffix not in {".json", ".csv"}:
            continue
        target = ROOT / record["path"]
        if target.exists():
            raise FileExistsError(f"Recovery refuses to overwrite {target}")
        blob = subprocess.check_output(["git", "show", f"HEAD~1:{record['path']}"], cwd=ROOT)
        if hashlib.sha256(blob).hexdigest() != record["previous_sha256"]:
            raise ValueError("Git source changed after inventory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        recovered.append(
            {
                "path": record["path"],
                "sha256": sha(target),
                "source_commit": git("rev-parse", "HEAD~1"),
                "purpose": "preserve_unique_historical_summary_or_per_image_evidence; not_current_result",
            }
        )
    write_json(
        output / "selective_recovery.json",
        {
            "performed_at": datetime.now(UTC).isoformat(),
            "command": "python scripts/audit_milestone3_evidence.py --restore-history --output "
            + output.relative_to(ROOT).as_posix(),
            "files": recovered,
            "count": len(recovered),
        },
    )
    print("selectively_recovered:", len(recovered))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-only", action="store_true")
    parser.add_argument("--restore-history", action="store_true")
    args = parser.parse_args()
    output = ROOT / args.output
    if args.restore_history:
        recover_history(output)
        return
    output.mkdir(parents=True, exist_ok=False)
    if not args.data_only:
        inventory(output)
    data_audit(output)
    print(output)
    result = json.loads((output / "dataset_audit.json").read_text(encoding="utf-8"))
    print(json.dumps({k: v for k, v in result.items() if k not in {"errors", "protected_hashes"}}, indent=2))
    print("canonical_errors:", len(result["errors"]))


if __name__ == "__main__":
    main()
