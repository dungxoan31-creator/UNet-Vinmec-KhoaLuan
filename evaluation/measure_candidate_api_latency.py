"""Measure candidate API latency on one image verified to belong to Validation."""

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def measure(base_url: str, validation_csv: Path, image_path: Path, manifest_path: Path, output: Path, repeats: int):
    validation_csv = validation_csv.resolve()
    image_path = image_path.resolve()
    with validation_csv.open(newline="", encoding="utf-8") as stream:
        validation_rows = list(csv.DictReader(stream))
    if not any((ROOT / row["image_path"]).resolve() == image_path for row in validation_rows):
        raise ValueError(f"Image is not listed in Validation CSV: {image_path}")

    selection = json.loads(manifest_path.read_text(encoding="utf-8"))
    client = httpx.Client(base_url=base_url, timeout=120)
    study_id = None
    try:
        with image_path.open("rb") as image_file:
            uploaded = client.post("/api/upload", files={"file": (image_path.name, image_file, "image/jpeg")})
        uploaded.raise_for_status()
        upload_data = uploaded.json()
        image_id, study_id = upload_data["image_id"], upload_data["study_id"]

        warmup = client.post(f"/api/predict/{image_id}")
        warmup.raise_for_status()
        prediction = warmup.json()
        checksum = prediction["provenance"]["model_checksum"]
        if checksum != selection["checkpoint_sha256"]:
            raise RuntimeError(f"API checkpoint mismatch: {checksum}")

        api_ms, end_to_end_ms = [], []
        for _ in range(repeats):
            started = time.perf_counter()
            response = client.post(f"/api/predict/{image_id}")
            elapsed = (time.perf_counter() - started) * 1000
            response.raise_for_status()
            prediction = response.json()
            if prediction["provenance"]["model_checksum"] != checksum:
                raise RuntimeError("Checkpoint changed during latency sampling")
            api_ms.append(float(prediction["inference_time_ms"]))
            end_to_end_ms.append(elapsed)
    finally:
        if study_id:
            client.delete(f"/api/cases/{study_id}")
        client.close()

    result = {
        "status": "measured",
        "split": "validation",
        "validation_csv": str(validation_csv.relative_to(ROOT)),
        "image": str(image_path.relative_to(ROOT)),
        "selection_manifest": str(manifest_path.relative_to(ROOT)),
        "checkpoint_sha256": checksum,
        "threshold": selection["threshold"],
        "input_normalization": selection["input_normalization"],
        "warmup_requests": 1,
        "measured_requests": repeats,
        "sampling_scope": "Repeated API requests for one Validation image; descriptive latency sample only.",
        "api_reported_ms": api_ms,
        "api_reported_median_ms": statistics.median(api_ms),
        "api_reported_p95_ms": percentile(api_ms, 0.95),
        "client_end_to_end_ms": [round(value, 3) for value in end_to_end_ms],
        "client_end_to_end_median_ms": round(statistics.median(end_to_end_ms), 3),
        "client_end_to_end_p95_ms": round(percentile(end_to_end_ms, 0.95), 3),
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8011")
    parser.add_argument("--validation-csv", type=Path, default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06/val.csv"))
    parser.add_argument("--image", type=Path, default=Path("dataset/Vinmec/Vinmec_2d/images/1098.JPG"))
    parser.add_argument("--manifest", type=Path, default=Path("evaluation/selected_model_unetplusplus_candidate.json"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/milestone_3_2026-10-06/api_latency_validation_unetplusplus_candidate.json"))
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    measure(args.base_url, ROOT / args.validation_csv, ROOT / args.image, ROOT / args.manifest,
            ROOT / args.output, args.repeats)


if __name__ == "__main__":
    main()
