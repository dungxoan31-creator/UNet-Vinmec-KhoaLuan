import copy
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers.auth import get_current_user
from backend.db import database
from backend.db.database import (
    AuditLogModel,
    HITLEventModel,
    HITLSessionModel,
    ImageModel,
    PatientModel,
    PredictionModel,
    StudyModel,
    UserModel,
)
from backend.services.inference_engine import InferenceEngine


@pytest.fixture
def candidate_case():
    db = next(database.get_db())
    patient_id = str(uuid.uuid4())
    study_id = str(uuid.uuid4())
    image_left_id = str(uuid.uuid4())
    image_right_id = str(uuid.uuid4())
    prediction_left_id = str(uuid.uuid4())
    prediction_right_id = str(uuid.uuid4())
    mask = {"shape": [512, 512], "first_val": 0, "counts": [1000, 200, 260944]}
    try:
        db.add(PatientModel(id=patient_id, anonymized_pid=f"CANDIDATE_{uuid.uuid4().hex[:12]}"))
        study = StudyModel(
            id=study_id,
            patient_id=patient_id,
            study_code=f"CAND_{uuid.uuid4().hex[:8]}",
            study_date="2026-10-25",
            status="ANALYZED",
            ovary_side="BOTH",
        )
        image_left = ImageModel(
            id=image_left_id,
            study_id=study_id,
            filename="left.png",
            laterality="L",
            raw_path="synthetic-left.png",
            width=512,
            height=512,
        )
        image_right = ImageModel(
            id=image_right_id,
            study_id=study_id,
            filename="right.png",
            laterality="R",
            raw_path="synthetic-right.png",
            width=512,
            height=512,
        )
        db.add_all([study, image_left, image_right])
        db.add_all([
            PredictionModel(
                id=prediction_left_id,
                image_id=image_left_id,
                model_version="CandidateTest-v1",
                raw_mask_rle=mask,
                measurements={},
            ),
            PredictionModel(
                id=prediction_right_id,
                image_id=image_right_id,
                model_version="CandidateTest-v1",
                raw_mask_rle=mask,
                measurements={},
            ),
        ])
        db.commit()
    finally:
        db.close()

    case = {
        "study_id": study_id,
        "img_l_id": image_left_id,
        "img_r_id": image_right_id,
        "pred_l_id": prediction_left_id,
        "pred_r_id": prediction_right_id,
        "ai_mask": mask,
    }
    try:
        yield case
    finally:
        db = next(database.get_db())
        try:
            study = db.query(StudyModel).filter_by(id=study_id).first()
            if study is not None:
                db.delete(study)
            patient = db.query(PatientModel).filter_by(id=patient_id).first()
            if patient is not None:
                db.delete(patient)
            db.commit()
        finally:
            db.close()


def candidate_payload(case, **overrides):
    payload = {
        "study_id": case["study_id"],
        "image_id": case["img_l_id"],
        "prediction_id": case["pred_l_id"],
        "min_component_area": 0,
        "closing_kernel_size": 0,
        "fill_holes": False,
        "smoothing_kernel_size": None,
    }
    payload.update(overrides)
    return payload


def stored_rows(case):
    db = next(database.get_db())
    try:
        study = db.query(StudyModel).filter(StudyModel.id == case["study_id"]).one()
        predictions = {
            prediction.id: prediction
            for prediction in db.query(PredictionModel)
            .filter(PredictionModel.id.in_([case["pred_l_id"], case["pred_r_id"]]))
            .all()
        }
        return {
            "study": (study.status, study.review_revision),
            "images": db.query(ImageModel).filter(ImageModel.study_id == case["study_id"]).count(),
            "predictions": db.query(PredictionModel).count(),
            "reviews": db.query(database.ReviewModel).count(),
            "audit_logs": db.query(AuditLogModel).count(),
            "hitl_sessions": db.query(HITLSessionModel).count(),
            "hitl_events": db.query(HITLEventModel).count(),
            "raw_masks": {key: copy.deepcopy(value.raw_mask_rle) for key, value in predictions.items()},
            "provenance": {key: copy.deepcopy(value.provenance_json) for key, value in predictions.items()},
        }
    finally:
        db.close()


def test_candidate_requires_clinical_access(candidate_case):
    body = candidate_payload(candidate_case)
    with TestClient(app) as client:
        assert client.post("/api/v1/segment/candidate", json=body).status_code == 401

        app.dependency_overrides[get_current_user] = lambda: UserModel(
            id="candidate-admin", username="admin", full_name="Admin", role="ADMIN"
        )
        try:
            denied = client.post("/api/v1/segment/candidate", json=body)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
    assert denied.status_code == 403


def test_candidate_uses_prediction_bound_to_image_and_study(
    candidate_case, doctor_access, monkeypatch
):
    left_mask = np.zeros((512, 512), dtype=np.uint8)
    left_mask[20:24, 30:34] = 1
    right_mask = np.zeros((512, 512), dtype=np.uint8)
    right_mask[80:84, 90:94] = 1
    db = next(database.get_db())
    try:
        left_prediction = db.query(PredictionModel).filter_by(id=candidate_case["pred_l_id"]).one()
        right_prediction = db.query(PredictionModel).filter_by(id=candidate_case["pred_r_id"]).one()
        left_prediction.raw_mask_rle = InferenceEngine.mask_to_rle(left_mask)
        right_prediction.raw_mask_rle = InferenceEngine.mask_to_rle(right_mask)
        db.commit()
    finally:
        db.close()

    from backend.app.config import model_registry

    monkeypatch.setattr(model_registry, "predict", lambda *args, **kwargs: pytest.fail("candidate endpoint reran inference"))
    with TestClient(app) as client:
        valid = client.post(
            "/api/v1/segment/candidate",
            json=candidate_payload(candidate_case),
        )
        cross_linked = client.post(
            "/api/v1/segment/candidate",
            json=candidate_payload(
                candidate_case,
                prediction_id=candidate_case["pred_r_id"],
            ),
        )

    assert valid.status_code == 200, valid.text
    response = valid.json()
    expected = InferenceEngine.mask_to_rle(left_mask)
    assert response["baseline_mask_rle"] == expected
    assert response["candidate_mask_rle"] == expected
    assert cross_linked.status_code == 404
    assert cross_linked.json()["detail"] == "Candidate source not found."


def test_candidate_returns_baseline_candidate_and_provenance(candidate_case, doctor_access):
    db = next(database.get_db())
    try:
        prediction = db.query(PredictionModel).filter_by(id=candidate_case["pred_l_id"]).one()
        prediction.provenance_json = {
            "checkpoint_sha256": "a" * 64,
            "patient_id": "must-not-be-returned",
            "device": "private-runtime-detail",
        }
        db.commit()
        expected_mask = copy.deepcopy(prediction.raw_mask_rle)
        expected_version = prediction.model_version
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/segment/candidate",
            json=candidate_payload(candidate_case),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["baseline_mask_rle"] == expected_mask
    np.testing.assert_array_equal(
        InferenceEngine.rle_to_mask(body["candidate_mask_rle"]),
        InferenceEngine.rle_to_mask(expected_mask),
    )
    assert body["candidate_parameters"] == {
        "min_component_area": 0,
        "closing_kernel_size": 0,
        "fill_holes": False,
        "smoothing_kernel_size": None,
    }
    assert body["provenance"] == {
        "prediction_id": candidate_case["pred_l_id"],
        "model_version": expected_version,
        "checkpoint_sha256": "a" * 64,
        "algorithm": "explicit_morphology_candidate",
        "algorithm_version": "1.0.0",
    }
    assert "patient_id" not in response.text
    assert "private-runtime-detail" not in response.text


def test_candidate_missing_or_cross_linked_prediction_is_rejected(candidate_case, doctor_access):
    cases = [
        candidate_payload(candidate_case, study_id=str(uuid.uuid4())),
        candidate_payload(candidate_case, image_id=str(uuid.uuid4())),
        candidate_payload(candidate_case, prediction_id=str(uuid.uuid4())),
        candidate_payload(candidate_case, prediction_id=candidate_case["pred_r_id"]),
    ]
    with TestClient(app) as client:
        responses = [
            client.post("/api/v1/segment/candidate", json=body)
            for body in cases
        ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404]
    assert {response.json()["detail"] for response in responses} == {
        "Candidate source not found."
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_component_area": -1},
        {"min_component_area": 262145},
        {"min_component_area": True},
        {"closing_kernel_size": 1},
        {"closing_kernel_size": 2},
        {"closing_kernel_size": 32},
        {"closing_kernel_size": True},
        {"fill_holes": 1},
        {"smoothing_kernel_size": 1},
        {"smoothing_kernel_size": 2},
        {"smoothing_kernel_size": 33},
        {"smoothing_kernel_size": True},
        {"study_id": ""},
        {"image_id": "x" * 37},
        {"unknown_client_mask": {"shape": [512, 512]}},
    ],
)
def test_candidate_parameters_are_bounded(candidate_case, doctor_access, overrides):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/segment/candidate",
            json=candidate_payload(candidate_case, **overrides),
        )
    assert response.status_code == 422, response.text


def test_candidate_endpoint_does_not_write(candidate_case, doctor_access):
    before = stored_rows(candidate_case)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/segment/candidate",
            json=candidate_payload(
                candidate_case,
                min_component_area=500,
                closing_kernel_size=3,
                fill_holes=True,
                smoothing_kernel_size=3,
            ),
        )
    after = stored_rows(candidate_case)

    assert response.status_code == 200, response.text
    assert response.json()["candidate_mask_rle"] != response.json()["baseline_mask_rle"]
    assert after == before
