"""Measure the local predict API on one validation image without touching test data."""

import argparse
import csv
import hashlib
import json
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.config import model_registry
from backend.app.main import app
from backend.app.routers import inference
from backend.db.database import Base, get_db


def milestone_1_validation_case(root: Path) -> dict[str, str]:
    split = root / "ai_training/splits/val.csv"
    with split.open(newline="", encoding="utf-8-sig") as split_file:
        for row in csv.DictReader(split_file):
            if (
                row["split"] == "VAL"
                and row["is_empty_mask"] == "False"
                and ("Vinmec_2D" in row["image_path"] or "vinmec_m1_307" in row["image_path"])
                and (root / row["image_path"]).is_file()
            ):
                return row
    raise ValueError(f"No usable Milestone 1 Validation image in {split}")



def main(output: Path = Path("evaluation/api_latency_validation.json")) -> None:
    root = Path(__file__).resolve().parents[1]
    case = milestone_1_validation_case(root)
    image_path = root / case["image_path"]
    adapter = model_registry.get_primary_adapter()
    if not adapter.is_loaded:
        raise RuntimeError("Selected checkpoint is unavailable or its checksum does not match")

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)
        db_engine = create_engine(
            f"sqlite:///{temporary_path / 'benchmark.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(db_engine)
        upload_dir = temporary_path / "uploads"
        upload_dir.mkdir()
        original_upload_dir = inference.UPLOAD_DIR
        inference.UPLOAD_DIR = str(upload_dir)

        def temporary_db():
            with Session(db_engine) as db:
                yield db

        app.dependency_overrides[get_db] = temporary_db
        try:
            with TestClient(app) as client:
                with image_path.open("rb") as image:
                    uploaded = client.post(
                        "/api/upload", files={"file": (image_path.name, image, "image/jpeg")}
                    )
                uploaded.raise_for_status()
                image_id = uploaded.json()["image_id"]
                durations_ms = []
                for iteration in range(6):
                    started = perf_counter()
                    response = client.post(f"/api/predict/{image_id}")
                    duration_ms = (perf_counter() - started) * 1000
                    response.raise_for_status()
                    if iteration:
                        durations_ms.append(duration_ms)
        finally:
            app.dependency_overrides.pop(get_db, None)
            inference.UPLOAD_DIR = original_upload_dir
            db_engine.dispose()

    result = {
        "split": "val",
        "case_id": case["case_id"],
        "source_split_csv": "ai_training/splits/val.csv",
        "checkpoint_sha256": hashlib.sha256(Path(adapter.weights_path).read_bytes()).hexdigest(),
        "device": adapter.device,
        "measurement": "TestClient POST /api/predict end-to-end, one warm-up excluded",
        "sample_count": len(durations_ms),
        "durations_ms": [round(duration, 2) for duration in durations_ms],
        "median_ms": round(statistics.median(durations_ms), 2),
        "p95_ms": round(statistics.quantiles(durations_ms, n=100, method="inclusive")[94], 2),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evaluation/api_latency_validation.json"))
    main(parser.parse_args().output)
