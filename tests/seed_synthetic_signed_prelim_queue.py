"""Seed synthetic read-only reviewer-queue rows in an isolated E2E database."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.db.database import (
    ImageModel,
    PatientModel,
    PredictionModel,
    ReviewModel,
    SessionLocal,
    StudyModel,
)


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 51
    if count < 1 or count > 100:
        raise SystemExit("count must be between 1 and 100")
    if len(sys.argv) != 3:
        raise SystemExit("usage: seed_synthetic_signed_prelim_queue.py COUNT FIXTURE_PNG")

    source_path = Path(sys.argv[2]).resolve(strict=True)
    source_bytes = source_path.read_bytes()
    content_hash = hashlib.sha256(source_bytes).hexdigest()
    upload_path = Path(os.environ["APP_DATA_DIR"]) / "uploads" / "synthetic-signed-queue.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, upload_path)
    mask_rle = {"shape": [512, 512], "first_val": 0, "counts": [1000, 200, 260944]}
    created_at = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=count)
    seeded = []
    with SessionLocal() as db:
        for index in range(count):
            patient_id = str(uuid.uuid4())
            study_id = str(uuid.uuid4())
            study_code = f"SYNTHETIC-SIGNED-{index + 1:04d}"
            db.add(
                PatientModel(
                    id=patient_id,
                    anonymized_pid=f"SYNTHETIC-QUEUE-{index + 1:04d}",
                    age_bucket=None,
                    menopausal_status=None,
                )
            )
            db.add(
                StudyModel(
                    id=study_id,
                    patient_id=patient_id,
                    study_code=study_code,
                    study_date="2026-10-29",
                    status="SIGNED_PRELIM",
                    ovary_side="LEFT",
                    contralateral_status="NOT_VISUALIZED",
                    review_revision=1,
                    created_at=created_at + timedelta(seconds=index),
                )
            )
            image_id = str(uuid.uuid4())
            prediction_id = str(uuid.uuid4())
            db.add(
                ImageModel(
                    id=image_id,
                    study_id=study_id,
                    filename=f"synthetic-signed-{index + 1:04d}.png",
                    laterality="L",
                    raw_path=str(upload_path),
                    file_hash=content_hash,
                    source_content_sha256=content_hash,
                    width=512,
                    height=512,
                )
            )
            db.add(
                PredictionModel(
                    id=prediction_id,
                    image_id=image_id,
                    model_version="synthetic-fixture",
                    inference_time_ms=0,
                    confidence_score=1.0,
                    iqa_score=1.0,
                    raw_mask_rle=mask_rle,
                    measurements={},
                    provenance_json={"status": "SYNTHETIC", "model_name": "synthetic-fixture"},
                )
            )
            db.add(
                ReviewModel(
                    id=str(uuid.uuid4()),
                    image_id=image_id,
                    prediction_id=prediction_id,
                    doctor_id="synthetic-reviewer",
                    doctor_action="ACCEPTED_RAW",
                    verified_mask_rle=mask_rle,
                    max_diameter_mm=0.0,
                    ortho_diameter_mm=0.0,
                    total_area_cm2=0.0,
                    lesion_type="UNSPECIFIED",
                    clinical_notes="",
                    hitl_feedback={"data_origin": "synthetic_fixture"},
                    is_official_ground_truth=False,
                    created_at=created_at + timedelta(seconds=index),
                )
            )
            seeded.append({"study_id": study_id, "study_code": study_code})
        db.commit()

    print(json.dumps(seeded, separators=(",", ":")))


if __name__ == "__main__":
    main()
