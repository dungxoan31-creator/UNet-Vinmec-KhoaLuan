"""Compare source-channel handling on local image-level validation data only.

The legacy disease service interpreted decoded BGR pixels as RGB. Reversing BGR
before the canonical BGR preprocessor reconstructs that legacy color transform.
This validation partition was previously used for model selection: it is not an
independent test or clinical performance estimate.
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def evaluate():
    from ai_training.mmotu_label_schema import MMOTU_8_CLASSES
    from ai_training.train_classifier_8class import parse_class_labels, validate_image_level_partitions
    from backend.services.image_classifier import CHECKSUM, ResearchImageClassifier

    train = parse_class_labels(ROOT / "metadata/mmotu_2d_train_cls.txt", ROOT / "dataset/2d/images")
    val = parse_class_labels(ROOT / "metadata/mmotu_2d_val_cls.txt", ROOT / "dataset/2d/images")
    split_audit = validate_image_level_partitions(train, val)
    hashes = [record["image_sha256"] for record in val]
    if len(hashes) != len(set(hashes)):
        raise ValueError("Validation contains duplicate image SHA-256 hashes")
    classifier = ResearchImageClassifier()
    results = {"legacy_bgr_interpreted_as_rgb": [], "training_parity_bgr": []}
    labels = []
    started = time.perf_counter()
    for index, row in enumerate(val):
        pixels = cv2.imdecode(np.fromfile(row["image_path"], dtype=np.uint8), cv2.IMREAD_COLOR)
        labels.append(row["label"])
        for key, image in (("legacy_bgr_interpreted_as_rgb", cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)),
                           ("training_parity_bgr", pixels)):
            result = classifier.predict(image)
            if result["status"] not in {"PREDICTED", "ABSTAIN"}:
                raise RuntimeError(f"Classifier unavailable: {result}")
            scores = result["probabilities"]
            predicted = max(scores, key=scores.get)
            results[key].append((MMOTU_8_CLASSES.index(predicted), result["status"] == "PREDICTED"))
        if (index + 1) % 100 == 0:
            print(f"Evaluated {index + 1}/{len(val)} image-level validation samples", flush=True)
    metrics = {}
    for key, rows in results.items():
        predictions = [row[0] for row in rows]
        accepted = [index for index, row in enumerate(rows) if row[1]]
        metrics[key] = {
            "top1_accuracy_all_images": accuracy_score(labels, predictions),
            "macro_f1_all_images": f1_score(labels, predictions, labels=list(range(8)), average="macro", zero_division=0),
            "confusion_matrix": confusion_matrix(labels, predictions, labels=list(range(8))).tolist(),
            "accepted_count": len(accepted), "abstained_count": len(rows) - len(accepted),
            "coverage": len(accepted) / len(rows),
            "accuracy_on_accepted_images": accuracy_score([labels[i] for i in accepted], [predictions[i] for i in accepted]) if accepted else None,
        }
    output = {
        "evidence_kind": "LOCAL_IMAGE_LEVEL_VALIDATION_PREPROCESSING_COMPARISON",
        "source_status": "PARTIALLY VERIFIED: local image bytes and label files checked; independent clinical label adjudication and redistribution rights not established",
        "checkpoint_sha256": CHECKSUM, "split_audit": split_audit,
        "validation_count": len(val), "device": "cpu", "elapsed_seconds": time.perf_counter() - started,
        "validation_order_sha256": hashlib.sha256("\n".join(hashes).encode()).hexdigest(),
        "metrics": metrics,
        "changed_top1_count": sum(a[0] != b[0] for a, b in zip(*results.values(), strict=True)),
        "patient_level_independence_verified": False, "independent_test": False,
        "limitations": "Validation used in prior checkpoint selection; no new training, no diagnostic probability calibration or clinical validation. Comparand reconstructs former RGB interpretation on OpenCV BGR source pixels; not a baseline clinical model.",
    }
    target = ROOT / "artifacts/resource_audit/classifier_preprocessing_validation.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k != "split_audit"}, indent=2), flush=True)


if __name__ == "__main__":
    evaluate()
