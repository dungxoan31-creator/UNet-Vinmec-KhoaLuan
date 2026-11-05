import csv
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import evaluation


def _write_sample_index(
    path, *, case_id, image_path, mask_path, row_overrides=None, omit_columns=()
):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        fieldnames = (
            "case_id",
            "image_path",
            "mask_path",
            "dice",
            "iou",
            "recall",
            "precision",
            "specificity",
            "tp",
            "fp",
            "fn",
            "tn",
        )
        fieldnames = tuple(name for name in fieldnames if name not in omit_columns)
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        row = {
            "case_id": case_id,
            "image_path": image_path,
            "mask_path": mask_path,
            "dice": 0.5,
            "iou": 0.4,
            "recall": 0.5,
            "precision": 0.5,
            "specificity": 0.5,
            "tp": 1,
            "fp": 1,
            "fn": 1,
            "tn": 1,
        }
        row.update(row_overrides or {})
        writer.writerow({name: row.get(name) for name in fieldnames})


def _write_metrics_fixture(tmp_path, monkeypatch):
    project = tmp_path / "project"
    evaluation_root = project / "evaluation"
    evaluation_root.mkdir(parents=True)
    files = {
        "validation": evaluation_root / "validation.json",
        "test": evaluation_root / "test.json",
        "manifest": evaluation_root / "manifest.json",
    }
    contents = {
        "validation": {
            "count": 1,
            "dice_mean_all_cases": 0.8,
            "iou_mean_all_cases": 0.7,
            "recall_mean_all_cases": 0.8,
            "checkpoint_sha256": "a" * 64,
            "clinical_summary": {
                "foreground_dice_std": 0.1,
                "foreground_iou_std": 0.1,
                "precision_mean": 0.8,
                "specificity_all_cases": 0.9,
            },
        },
        "test": {
            "test_count": 1,
            "checkpoint_sha256": "b" * 64,
            "patient_level_independence_verified": False,
            "mean_per_image": {
                "dice": 0.8,
                "iou": 0.7,
                "recall": 0.8,
                "precision": 0.8,
                "specificity_background_pixels": 0.9,
                "specificity_normal_cases": None,
            },
        },
        "manifest": {"counts": {"train": 2}},
    }
    for name, path in files.items():
        path.write_text(json.dumps(contents[name]), encoding="utf-8")

    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))
    monkeypatch.setattr(evaluation, "VAL_SUMMARY_PATH", str(files["validation"]))
    monkeypatch.setattr(evaluation, "TEST_METRICS_PATH", str(files["test"]))
    monkeypatch.setattr(evaluation, "SPLIT_MANIFEST_PATH", str(files["manifest"]))
    monkeypatch.setattr(evaluation, "CURRENT_RUN_PATH", str(evaluation_root / "missing-current.json"))
    monkeypatch.setattr(evaluation, "RELEASE_STATUS_PATH", str(evaluation_root / "missing-release.json"))
    return files


def _valid_current_run_summary():
    metric_names = ("dice", "iou", "recall", "precision", "specificity", "hd95_px")
    primary = {
        name: {
            "mean": 0.75,
            "median": 0.75,
            "std": 0.1,
            "min": 0.5,
            "max": 0.9,
            "n_valid": 2,
            "n_null": 0,
        }
        for name in metric_names
    }
    primary["hd95_px"].update(mean=2.0, median=2.0, min=1.0, max=3.0)
    return {
        "schema_version": 1,
        "run_id": "legacy_test_v1",
        "run_kind": "retrospective_test_replay",
        "status": "COMPLETE",
        "checkpoint_sha256": "c" * 64,
        "protocol_sha256": "d" * 64,
        "manifest_sha256": "e" * 64,
        "counts": {"total_samples": 2, "nonempty_gt_samples": 2, "empty_gt_samples": 0},
        "primary": primary,
        "secondary": {
            "all_images_agreement_dice": {"mean": 0.75},
            "micro_dice": 0.75,
            "micro_iou": 0.6,
        },
    }


def _write_current_run_pointer(evaluation_root, summary_path):
    pointer = evaluation_root / "current_run.json"
    pointer.write_text(
        json.dumps(
            {
                "summary_path": str(summary_path.relative_to(evaluation_root.parent)).replace("\\", "/"),
                "run_id": "legacy_test_v1",
                "run_kind": "retrospective_test_replay",
                "status": "COMPLETE",
                "checkpoint_sha256": "c" * 64,
                "protocol_sha256": "d" * 64,
                "manifest_sha256": "e" * 64,
            }
        ),
        encoding="utf-8",
    )
    return pointer


def test_sample_source_resolver_rejects_paths_outside_project_root(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "outside.jpg").write_bytes(b"private image bytes")
    (tmp_path / "outside.png").write_bytes(b"private mask bytes")
    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))
    with pytest.raises(HTTPException) as error:
        evaluation._resolve_sample_source("../outside.jpg")
    assert error.value.status_code == 404


def test_sample_source_resolver_rejects_project_files_outside_dataset_root(tmp_path, monkeypatch):
    project = tmp_path / "project"
    private_file = project / "backend" / ".env"
    private_file.parent.mkdir(parents=True)
    private_file.write_text("private configuration", encoding="utf-8")
    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))
    with pytest.raises(HTTPException) as error:
        evaluation._resolve_sample_source("backend/.env")
    assert error.value.status_code == 404


def test_prediction_mask_resolver_rejects_traversal_in_case_id(tmp_path, monkeypatch):
    project = tmp_path / "project"
    prediction_dir = project / "evaluation" / "predictions"
    prediction_dir.mkdir(parents=True)
    (project / "evaluation" / "outside.png").write_bytes(b"private prediction bytes")
    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))
    monkeypatch.setattr(evaluation, "PRED_MASKS_DIR", str(prediction_dir))
    with pytest.raises(HTTPException) as error:
        evaluation._resolve_prediction_mask("..\\outside")
    assert error.value.status_code == 404


def test_sample_source_resolver_does_not_alias_missing_legacy_source_to_other_dataset(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    relocated = project / "dataset" / "2d" / "images" / "sample.jpg"
    relocated.parent.mkdir(parents=True)
    relocated.write_bytes(b"different dataset image")
    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))

    with pytest.raises(HTTPException) as error:
        evaluation._resolve_sample_source(
            "dataset/Vinmec_2D/train/train_image/sample.jpg"
        )

    assert error.value.status_code == 503
    assert error.value.detail == "Evaluation sample source files are unavailable."


def test_metrics_does_not_read_summary_outside_evaluation_root(
    tmp_path, monkeypatch, evaluation_reviewer_access
):
    project = tmp_path / "project"
    evaluation_root = project / "evaluation"
    evaluation_root.mkdir(parents=True)
    private_summary = project / "backend" / "private-summary.json"
    private_summary.parent.mkdir(parents=True)
    private_summary.write_text(
        '{"counts":{"private":"synthetic-secret"},'
        '"primary":{"dice":{"mean":"synthetic-secret"}}}',
        encoding="utf-8",
    )
    pointer = evaluation_root / "current_run.json"
    pointer.write_text(json.dumps({"summary_path": str(private_summary)}), encoding="utf-8")
    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))
    monkeypatch.setattr(evaluation, "CURRENT_RUN_PATH", str(pointer))
    monkeypatch.setattr(evaluation, "VAL_SUMMARY_PATH", str(evaluation_root / "missing-validation.json"))
    monkeypatch.setattr(evaluation, "TEST_METRICS_PATH", str(evaluation_root / "missing-test.json"))
    monkeypatch.setattr(evaluation, "SPLIT_MANIFEST_PATH", str(evaluation_root / "missing-manifest.json"))
    monkeypatch.setattr(evaluation, "RELEASE_STATUS_PATH", str(evaluation_root / "missing-release.json"))

    with TestClient(app) as client:
        response = client.get("/api/evaluation/metrics")

    assert response.status_code == 200
    assert response.json()["current_run"] is None


def test_metrics_reports_missing_current_run_summary_without_claiming_completion(
    tmp_path, monkeypatch, evaluation_reviewer_access
):
    _write_metrics_fixture(tmp_path, monkeypatch)
    evaluation_root = tmp_path / "project" / "evaluation"
    pointer = evaluation_root / "current_run.json"
    pointer.write_text(
        json.dumps(
            {
                "summary_path": "evaluation/runs/legacy_test_v1/summary.json",
                "run_id": "legacy_test_v1",
                "run_kind": "retrospective_test_replay",
                "status": "COMPLETE",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluation, "CURRENT_RUN_PATH", str(pointer))

    with TestClient(app) as client:
        response = client.get("/api/evaluation/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_run"] is None
    assert payload["current_run_status"] == {
        "run_id": "legacy_test_v1",
        "status": "ARTIFACT_MISSING",
        "artifact_available": False,
    }


@pytest.mark.parametrize(
    "invalid_case",
    ["missing_metrics_section", "metric_out_of_range", "invalid_sample_count", "checkpoint_hash_mismatch"],
)
def test_metrics_withholds_current_run_with_invalid_summary_integrity(
    tmp_path, monkeypatch, evaluation_reviewer_access, invalid_case
):
    _write_metrics_fixture(tmp_path, monkeypatch)
    evaluation_root = tmp_path / "project" / "evaluation"
    summary = _valid_current_run_summary()
    if invalid_case == "missing_metrics_section":
        summary.pop("primary")
    elif invalid_case == "metric_out_of_range":
        summary["primary"]["dice"]["mean"] = 1.01
    elif invalid_case == "invalid_sample_count":
        summary["counts"]["total_samples"] = -1
    elif invalid_case == "checkpoint_hash_mismatch":
        summary["checkpoint_sha256"] = "f" * 64
    summary_path = evaluation_root / "runs" / "legacy_test_v1" / "summary.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    pointer = _write_current_run_pointer(evaluation_root, summary_path)
    monkeypatch.setattr(evaluation, "CURRENT_RUN_PATH", str(pointer))

    with TestClient(app) as client:
        response = client.get("/api/evaluation/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_run"] is None
    assert payload["current_run_status"] == {
        "run_id": "legacy_test_v1",
        "status": "ARTIFACT_INVALID",
        "artifact_available": False,
    }


def test_metrics_loads_current_run_only_after_summary_integrity_validation(
    tmp_path, monkeypatch, evaluation_reviewer_access
):
    _write_metrics_fixture(tmp_path, monkeypatch)
    evaluation_root = tmp_path / "project" / "evaluation"
    summary_path = evaluation_root / "runs" / "legacy_test_v1" / "summary.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(json.dumps(_valid_current_run_summary()), encoding="utf-8")
    pointer = _write_current_run_pointer(evaluation_root, summary_path)
    monkeypatch.setattr(evaluation, "CURRENT_RUN_PATH", str(pointer))

    with TestClient(app) as client:
        response = client.get("/api/evaluation/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_run_status"] == {
        "run_id": "legacy_test_v1",
        "status": "AVAILABLE",
        "artifact_available": True,
    }
    assert payload["current_run"]["primary"]["dice"]["mean"] == 0.75


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dice", ""),
        ("dice", "nan"),
        ("dice", "inf"),
        ("iou", "1.01"),
        ("tp", "-1"),
        ("fp", "1.5"),
    ],
)
def test_evaluation_samples_reject_malformed_metrics_and_counts(
    tmp_path, monkeypatch, evaluation_reviewer_access, field, value
):
    index = tmp_path / "samples.csv"
    _write_sample_index(
        index,
        case_id="fixture-case",
        image_path="dataset/image.jpg",
        mask_path="dataset/mask.png",
        row_overrides={field: value},
    )
    monkeypatch.setattr(evaluation, "PER_IMAGE_CSV_PATH", str(index))

    with pytest.raises(HTTPException) as error:
        evaluation._read_evaluation_sample_rows()
    assert error.value.status_code == 503


def test_evaluation_samples_reject_missing_metric_columns(
    tmp_path, monkeypatch, evaluation_reviewer_access
):
    index = tmp_path / "samples.csv"
    _write_sample_index(
        index,
        case_id="fixture-case",
        image_path="dataset/image.jpg",
        mask_path="dataset/mask.png",
        omit_columns=("precision",),
    )
    monkeypatch.setattr(evaluation, "PER_IMAGE_CSV_PATH", str(index))

    with pytest.raises(HTTPException) as error:
        evaluation._read_evaluation_sample_rows()
    assert error.value.status_code == 503


def test_evaluation_sample_list_fails_closed_when_provenance_is_unverified(
    tmp_path, monkeypatch, evaluation_reviewer_access
):
    project = tmp_path / "project"
    project.mkdir()
    index = tmp_path / "samples.csv"
    _write_sample_index(
        index,
        case_id="fixture-case",
        image_path="dataset/image.jpg",
        mask_path="dataset/mask.png",
    )
    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))
    monkeypatch.setattr(evaluation, "PER_IMAGE_CSV_PATH", str(index))

    with TestClient(app) as client:
        response = client.get("/api/evaluation/samples")

    assert response.status_code == 503
    assert "provenance" in response.json()["detail"].lower()


def test_workstation_bundle_rejects_out_of_range_benchmark_metric(
    tmp_path, monkeypatch, evaluation_reviewer_access
):
    project = tmp_path / "project"
    dataset = project / "dataset"
    dataset.mkdir(parents=True)
    (dataset / "image.jpg").write_bytes(b"image")
    (dataset / "mask.png").write_bytes(b"mask")
    index = tmp_path / "samples.csv"
    _write_sample_index(
        index,
        case_id="fixture-case",
        image_path="dataset/image.jpg",
        mask_path="dataset/mask.png",
        row_overrides={"dice": "1.01"},
    )
    monkeypatch.setattr(evaluation, "BASE_DIR", str(project))
    monkeypatch.setattr(evaluation, "PER_IMAGE_CSV_PATH", str(index))
    monkeypatch.setattr(evaluation, "PRED_MASKS_DIR", str(project / "predictions"))

    with pytest.raises(HTTPException) as error:
        evaluation._read_evaluation_sample_rows()
    assert error.value.status_code == 503


@pytest.mark.parametrize(
    ("artifact", "payload"),
    [
        ("manifest", "{"),
        ("manifest", "[]"),
        ("manifest", '{"counts":[]}'),
        ("manifest", '{"counts":{"train":-1}}'),
        ("validation", "[]"),
        ("validation", '{"clinical_summary":[]}'),
        ("validation", '{"dice_mean_all_cases":NaN,"clinical_summary":{}}'),
        ("validation", '{"dice_mean_all_cases":1.01,"clinical_summary":{}}'),
        ("test", '{"mean_per_image":[]}'),
        ("test", '{"mean_per_image":{"dice":-0.1}}'),
    ],
)
def test_metrics_withhold_legacy_values_without_reading_archive_artifacts(
    tmp_path, monkeypatch, evaluation_reviewer_access, artifact, payload
):
    files = _write_metrics_fixture(tmp_path, monkeypatch)
    files[artifact].write_text(payload, encoding="utf-8")

    with TestClient(app) as client:
        response = client.get("/api/evaluation/metrics")

    assert response.status_code == 200
    result = response.json()
    assert result["archived_split_status"]["status"] == "BLOCKED"
    assert result["validation"]["count"] is None
    assert result["validation"]["dice_mean"] is None
    assert result["test"]["count"] is None
    assert result["test"]["dice_mean"] is None
