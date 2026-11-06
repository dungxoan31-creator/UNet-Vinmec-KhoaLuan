"""Persisted per-region RUO measurements and CDSS provenance tests."""

import hashlib
import uuid
from datetime import datetime

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.db.database import (
    Base,
    ImageModel,
    PatientModel,
    PredictionModel,
    RegionAssignmentBatchModel,
    RegionCaliperEventModel,
    RegionCDSSAssessmentModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.services.inference_engine import InferenceEngine

pytestmark = pytest.mark.usefixtures("doctor_access")


@pytest.fixture
def region_clinical_case(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'region-clinical.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    patient_id, study_id, image_id, prediction_id, review_id = [str(uuid.uuid4()) for _ in range(5)]
    mask = np.zeros((512, 512), dtype=np.uint8)
    cv2.rectangle(mask, (10, 20), (40, 50), 1, -1)
    cv2.rectangle(mask, (200, 300), (220, 320), 1, -1)
    rle = InferenceEngine.mask_to_rle(mask)
    with Session(engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.add(PatientModel(id=patient_id, anonymized_pid="SYNTHETIC-REGION-CLINICAL"))
        db.add(StudyModel(id=study_id, patient_id=patient_id, study_date="2026-10-28"))
        db.add(ImageModel(
            id=image_id, study_id=study_id, filename="synthetic.png", raw_path="unused.png", laterality="L",
            width=512, height=512, pixel_spacing_mm=0.1, calibration_source="MANUAL",
        ))
        db.add(PredictionModel(id=prediction_id, image_id=image_id, raw_mask_rle=rle, measurements={}))
        db.add(ReviewModel(
            id=review_id, image_id=image_id, prediction_id=prediction_id,
            doctor_action="ACCEPTED_RAW", verified_mask_rle=rle,
        ))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            yield client, engine, study_id, image_id, review_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def confirm_regions(client, active_case_lease, study_id, image_id, review_id):
    review_base = f"/api/cases/{study_id}/images/{image_id}/reviews/{review_id}"
    candidates = client.get(review_base + "/region-candidates")
    assert candidates.status_code == 200, candidates.text
    data = candidates.json()
    lease = active_case_lease(client, study_id)
    response = client.post(review_base + "/region-assignments", json={
        "request_id": str(uuid.uuid4()),
        "expected_revision": 0,
        "mask_sha256": data["mask_sha256"],
        "confirmed": True,
        "assignments": [{"component_index": item["component_index"]} for item in data["components"]],
        **lease,
    })
    assert response.status_code == 200, response.text
    assignments = client.get(f"/api/cases/{study_id}/images/{image_id}/region-assignments")
    assert assignments.status_code == 200, assignments.text
    snapshot = assignments.json()["assignment"]
    assert snapshot["assignment_request_id"] == response.json()["assignment_request_id"]
    first = snapshot["assignments"][0]
    return data, snapshot, first, lease


def measurement_path(study_id, image_id, region_id):
    return f"/api/cases/{study_id}/images/{image_id}/regions/{region_id}/calipers"


def assessment_path(study_id, image_id, region_id):
    return f"/api/cases/{study_id}/images/{image_id}/regions/{region_id}/cdss-assessments"


def region_query(snapshot, review_id):
    return {
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "mask_sha256": snapshot["mask_sha256"],
    }


def make_caliper(snapshot, review_id, region_id, lease, *, revision, points, label="D1", request_id=None):
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "expected_revision": revision,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region_id,
        "mask_sha256": snapshot["mask_sha256"],
        "label": label,
        "points": points,
        "coordinate_space": "decoded-source-image",
        **lease,
    }


def test_caliper_is_region_bound_source_coordinate_calibrated_and_reloadable(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    base = measurement_path(study_id, image_id, region["region_id"])
    query = region_query(snapshot, review_id)
    payload = make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[10, 20], [40, 20]],
    )

    saved = client.post(base, json=payload)
    assert saved.status_code == 200, saved.text
    event = saved.json()
    assert event["coordinate_space"] == "decoded-source-image"
    assert event["points"] == [[10.0, 20.0], [40.0, 20.0]]
    assert event["diameter_px"] == 30
    assert event["diameter_mm"] == 3
    assert event["calibration_source"] == "MANUAL"
    assert event["current"] is True
    assert event["usable_for_cdss"] is True

    replay = client.post(base, json=payload)
    assert replay.status_code == 200
    assert replay.json()["request_id"] == event["request_id"]
    assert replay.json()["diameter_mm"] == 3

    loaded = client.get(base, params=query)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["measurements"]["D1"]["request_id"] == event["request_id"]
    assert len(loaded.json()["history"]) == 1

    tampered = make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=1, points=[[200, 300], [220, 300]],
    )
    outside_region = client.post(base, json=tampered)
    assert outside_region.status_code == 422
    assert "đúng vùng" in outside_region.json()["detail"]


def test_region_caliper_maps_nonsquare_source_points_to_letterbox_region(
    region_clinical_case, active_case_lease,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    candidates, snapshot, _first_region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    with Session(engine) as db:
        image = db.get(ImageModel, image_id)
        image.width = 640
        image.height = 480
        db.commit()

    target_component = next(
        component for component in candidates["components"]
        if component["bounding_box_xywh"][:2] == [200, 300]
    )
    region = next(
        assignment for assignment in snapshot["assignments"]
        if assignment["component_index"] == target_component["component_index"]
    )

    # Source pixels [250, 307.5] → [275, 307.5] map to model pixels
    # [200, 310] → [220, 310] in the 512×512 letterboxed review mask.
    payload = make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[250, 307.5], [275, 307.5]],
    )
    response = client.post(
        measurement_path(study_id, image_id, region["region_id"]),
        json=payload,
    )

    assert response.status_code == 200, response.text
    event = response.json()
    assert event["coordinate_space"] == "decoded-source-image"
    assert event["points"] == [[250.0, 307.5], [275.0, 307.5]]
    assert event["diameter_px"] == 25
    assert event["diameter_mm"] == 2.5
    assert event["region_id"] == region["region_id"]
    assert event["current"] is True
    assert event["usable_for_cdss"] is True


def test_two_disjoint_components_keep_independent_region_calipers(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    candidates, snapshot, _first_region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    assert len(candidates["components"]) == 2
    assert len(snapshot["assignments"]) == 2
    assert len({row["region_id"] for row in snapshot["assignments"]}) == 2

    components_by_location = {
        tuple(component["bounding_box_xywh"][:2]): component
        for component in candidates["components"]
    }
    assignments_by_component = {
        row["component_index"]: row for row in snapshot["assignments"]
    }
    cases = [
        ((10, 20), [[10, 25], [40, 25]], 30),
        ((200, 300), [[200, 310], [220, 310]], 20),
    ]
    saved_events = []
    for location, points, expected_diameter_px in cases:
        component = components_by_location[location]
        region = assignments_by_component[component["component_index"]]
        path = measurement_path(study_id, image_id, region["region_id"])
        response = client.post(
            path,
            json=make_caliper(
                snapshot, review_id, region["region_id"], lease,
                revision=0, points=points,
            ),
        )
        assert response.status_code == 200, response.text
        event = response.json()
        assert event["region_id"] == region["region_id"]
        assert event["diameter_px"] == expected_diameter_px
        assert event["diameter_mm"] == expected_diameter_px * 0.1
        assessment_path_for_region = assessment_path(study_id, image_id, region["region_id"])
        assessment_payload = {
            "request_id": str(uuid.uuid4()),
            "expected_assessment_revision": 0,
            "assignment_request_id": snapshot["assignment_request_id"],
            "review_id": review_id,
            "region_id": region["region_id"],
            "mask_sha256": snapshot["mask_sha256"],
            "confirmed": True,
            "vision_findings": {
                "assessment_source": "clinician",
                "modality": "ultrasound_2d",
                "ultrasound_exam_complete": False,
                "max_diameter_mm": event["diameter_mm"],
            },
            "patient_context": {},
            "source_caliper_event_id": event["request_id"],
            **lease,
        }
        assessment = client.post(assessment_path_for_region, json=assessment_payload)
        assert assessment.status_code == 200, assessment.text
        assessment_body = assessment.json()
        assert assessment_body["region_id"] == region["region_id"]
        assert assessment_body["vision_findings"]["max_diameter_mm"] == event["diameter_mm"]
        assert assessment_body["source_caliper_event_id"] == event["request_id"]
        assert assessment_body["result"]["status"] == "INSUFFICIENT_DATA"
        assert assessment_body["result"]["orads_stratification"].get("category") is None
        saved_events.append((path, region, event, assessment_path_for_region, assessment_body))

    for path, region, event, assessment_path_for_region, assessment in saved_events:
        loaded = client.get(path, params=region_query(snapshot, review_id))
        assert loaded.status_code == 200, loaded.text
        current_d1 = loaded.json()["measurements"]["D1"]
        assert current_d1["region_id"] == region["region_id"]
        assert current_d1["request_id"] == event["request_id"]
        assert current_d1["diameter_mm"] == event["diameter_mm"]
        loaded_assessment = client.get(
            assessment_path_for_region,
            params=region_query(snapshot, review_id),
        )
        assert loaded_assessment.status_code == 200, loaded_assessment.text
        assert loaded_assessment.json()["latest"]["request_id"] == assessment["request_id"]
        assert loaded_assessment.json()["latest"]["region_id"] == region["region_id"]


def test_d1_d2_calipers_keep_independent_revisions_and_history(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    base = measurement_path(study_id, image_id, region["region_id"])
    query = region_query(snapshot, review_id)

    d1_payload = make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[10, 20], [40, 20]], label="D1",
    )
    d2_payload = make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[25, 20], [25, 50]], label="D2",
    )
    d1 = client.post(base, json=d1_payload)
    d2 = client.post(base, json=d2_payload)
    assert d1.status_code == d2.status_code == 200, (d1.text, d2.text)
    d1_event = d1.json()
    d2_event = d2.json()
    assert d1_event["measurement_revision"] == d2_event["measurement_revision"] == 1
    assert d1_event["diameter_px"] == d2_event["diameter_px"] == 30
    assert d1_event["diameter_mm"] == d2_event["diameter_mm"] == 3

    d1_updated = client.post(base, json=make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=1, points=[[10, 21], [30, 21]], label="D1",
    ))
    assert d1_updated.status_code == 200, d1_updated.text
    d1_updated_event = d1_updated.json()
    assert d1_updated_event["measurement_revision"] == 2
    assert d1_updated_event["diameter_px"] == 20

    reloaded = client.get(base, params=query)
    assert reloaded.status_code == 200, reloaded.text
    measurements = reloaded.json()["measurements"]
    assert measurements["D1"]["request_id"] == d1_updated_event["request_id"]
    assert measurements["D1"]["measurement_revision"] == 2
    assert measurements["D2"]["request_id"] == d2_event["request_id"]
    assert measurements["D2"]["measurement_revision"] == 1
    history = reloaded.json()["history"]
    assert len(history) == 3
    assert {event["label"] for event in history} == {"D1", "D2"}
    assert sum(event["current"] for event in history if event["label"] == "D1") == 1
    assert sum(event["current"] for event in history if event["label"] == "D2") == 1
    replayed_old_d1 = client.post(base, json=d1_payload)
    assert replayed_old_d1.status_code == 200, replayed_old_d1.text
    assert replayed_old_d1.json()["request_id"] == d1_event["request_id"]
    assert replayed_old_d1.json()["current"] is False
    assert replayed_old_d1.json()["usable_for_cdss"] is False


def test_latest_d2_is_not_hidden_by_a_capped_d1_history(
    region_clinical_case, active_case_lease,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    base = measurement_path(study_id, image_id, region["region_id"])
    query = region_query(snapshot, review_id)
    d1 = client.post(base, json=make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[10, 20], [40, 20]], label="D1",
    ))
    d2 = client.post(base, json=make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[25, 20], [25, 50]], label="D2",
    ))
    assert d1.status_code == d2.status_code == 200, (d1.text, d2.text)

    with Session(engine) as db:
        original = db.get(RegionCaliperEventModel, d1.json()["request_id"])
        for revision in range(2, 102):
            db.add(RegionCaliperEventModel(
                request_id=str(uuid.uuid4()),
                assignment_request_id=original.assignment_request_id,
                study_id=original.study_id,
                image_id=original.image_id,
                review_id=original.review_id,
                region_id=original.region_id,
                review_revision=original.review_revision,
                mask_sha256=original.mask_sha256,
                label="D1",
                measurement_revision=revision,
                coordinate_space=original.coordinate_space,
                points_json=original.points_json,
                source_width=original.source_width,
                source_height=original.source_height,
                diameter_px=original.diameter_px,
                diameter_mm=original.diameter_mm,
                pixel_spacing_mm=original.pixel_spacing_mm,
                calibration_source=original.calibration_source,
                calibration_hash=original.calibration_hash,
                actor_id=original.actor_id,
                request_hash=hashlib.sha256(str(revision).encode()).hexdigest(),
            ))
        db.commit()

    reloaded = client.get(base, params=query)
    assert reloaded.status_code == 200, reloaded.text
    body = reloaded.json()
    assert body["measurements"]["D1"]["measurement_revision"] == 101
    assert body["measurements"]["D2"]["request_id"] == d2.json()["request_id"]
    assert body["measurements"]["D2"]["measurement_revision"] == 1
    assert body["history_truncated"] is True
    assert body["history_has_more"] is True
    assert len(body["history"]) == 100
    assert body["history_next_cursor"]

    next_page = client.get(base, params={**query, "cursor": body["history_next_cursor"]})
    assert next_page.status_code == 200, next_page.text
    next_body = next_page.json()
    assert next_body["history_has_more"] is False
    assert next_body["history_next_cursor"] is None
    assert {event["request_id"] for event in next_body["history"]} == {
        d1.json()["request_id"], d2.json()["request_id"],
    }
    assert len({event["request_id"] for event in body["history"] + next_body["history"]}) == 102
    assert client.get(base, params={**query, "limit": 101}).status_code == 422
    assert client.get(base, params={**query, "cursor": "not-a-cursor"}).status_code == 422
    assessment_cursor = client.get(
        assessment_path(study_id, image_id, region["region_id"]),
        params={**query, "cursor": body["history_next_cursor"]},
    )
    assert assessment_cursor.status_code == 422


def test_cdss_assessment_saves_real_engine_result_and_exact_caliper_provenance(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    caliper = client.post(
        measurement_path(study_id, image_id, region["region_id"]),
        json=make_caliper(snapshot, review_id, region["region_id"], lease,
                          revision=0, points=[[10, 20], [40, 20]]),
    )
    assert caliper.status_code == 200, caliper.text
    event = caliper.json()

    payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": 3.0,
        },
        "patient_context": {},
        "source_caliper_event_id": event["request_id"],
        **lease,
    }
    base = assessment_path(study_id, image_id, region["region_id"])
    saved = client.post(base, json=payload)
    assert saved.status_code == 200, saved.text
    result = saved.json()
    assert result["status"] == "SAVED_RUO"
    assert result["assessment_revision"] == 1
    assert result["source_caliper_event_id"] == event["request_id"]
    assert result["source_caliper_revision"] == 1
    assert result["result"]["status"] == "INSUFFICIENT_DATA"
    assert result["result"]["orads_stratification"].get("category") is None

    query = region_query(snapshot, review_id)
    reloaded = client.get(base, params=query)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["latest"]["request_id"] == result["request_id"]
    assert reloaded.json()["latest"]["current"] is True
    assert reloaded.json()["latest"]["result"] == result["result"]

    replay = client.post(base, json=payload)
    assert replay.status_code == 200
    assert replay.json()["request_id"] == result["request_id"]
    assert replay.json()["assessment_revision"] == 1

    second_payload = {
        **payload,
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 1,
    }
    second = client.post(base, json=second_payload)
    assert second.status_code == 200, second.text
    assert second.json()["assessment_revision"] == 2
    history = client.get(base, params=query).json()["history"]
    assert [item["assessment_revision"] for item in history] == [2, 1]
    assert [item["current"] for item in history] == [True, False]
    replay_old = client.post(base, json=payload)
    assert replay_old.status_code == 200
    assert replay_old.json()["current"] is False


def test_assessment_save_response_is_stale_if_newer_revision_commits_first(
    region_clinical_case, active_case_lease, monkeypatch,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
        },
        "patient_context": {},
        **lease,
    }
    original_commit = Session.commit
    injected = False

    def commit_with_newer_assessment(db):
        nonlocal injected
        is_target = any(
            isinstance(row, RegionCDSSAssessmentModel) and row.request_id == payload["request_id"]
            for row in db.new
        )
        original_commit(db)
        if is_target and not injected:
            injected = True
            with Session(engine) as competing_db:
                competing_db.add(RegionCDSSAssessmentModel(
                    request_id=str(uuid.uuid4()),
                    assignment_request_id=snapshot["assignment_request_id"],
                    study_id=study_id,
                    image_id=image_id,
                    review_id=review_id,
                    region_id=region["region_id"],
                    review_revision=snapshot["review_revision"],
                    mask_sha256=snapshot["mask_sha256"],
                    assessment_revision=2,
                    vision_findings_json={"assessment_source": "clinician"},
                    patient_context_json={},
                    source_caliper_event_id=None,
                    source_caliper_revision=None,
                    result_json={"status": "INSUFFICIENT_DATA"},
                    actor_id="test-doctor",
                    request_hash="e" * 64,
                ))
                original_commit(competing_db)

    monkeypatch.setattr(Session, "commit", commit_with_newer_assessment)
    response = client.post(
        assessment_path(study_id, image_id, region["region_id"]),
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert injected is True
    assert response.json()["assessment_revision"] == 1
    assert response.json()["current"] is False


def test_assessment_ack_is_stale_if_source_caliper_changes_before_response(
    region_clinical_case, active_case_lease, monkeypatch,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    caliper_path = measurement_path(study_id, image_id, region["region_id"])
    original_caliper = client.post(
        caliper_path,
        json=make_caliper(snapshot, review_id, region["region_id"], lease,
                          revision=0, points=[[10, 20], [40, 20]]),
    )
    assert original_caliper.status_code == 200, original_caliper.text
    source = original_caliper.json()
    assessment_payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": source["diameter_mm"],
        },
        "patient_context": {},
        "source_caliper_event_id": source["request_id"],
        **lease,
    }
    original_commit = Session.commit
    injected = False

    def commit_then_update_source_caliper(db):
        nonlocal injected
        is_target = any(
            isinstance(row, RegionCDSSAssessmentModel)
            and row.request_id == assessment_payload["request_id"]
            for row in db.new
        )
        original_commit(db)
        if is_target and not injected:
            injected = True
            changed = client.post(
                caliper_path,
                json=make_caliper(snapshot, review_id, region["region_id"], lease,
                                  revision=1, points=[[11, 20], [39, 20]]),
            )
            assert changed.status_code == 200, changed.text

    monkeypatch.setattr(Session, "commit", commit_then_update_source_caliper)
    response = client.post(
        assessment_path(study_id, image_id, region["region_id"]),
        json=assessment_payload,
    )

    assert injected is True
    assert response.status_code == 200, response.text
    assert response.json()["current"] is False
    assert response.json()["stale_reason"]


def test_caliper_update_invalidates_linked_assessment_and_revision_races(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    cpath = measurement_path(study_id, image_id, region["region_id"])
    first = client.post(cpath, json=make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[10, 20], [40, 20]],
    ))
    assert first.status_code == 200, first.text

    apath = assessment_path(study_id, image_id, region["region_id"])
    assessment = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {"assessment_source": "clinician", "modality": "ultrasound_2d",
                            "ultrasound_exam_complete": False, "max_diameter_mm": 3.0},
        "patient_context": {},
        "source_caliper_event_id": first.json()["request_id"],
        **lease,
    }
    saved = client.post(apath, json=assessment)
    assert saved.status_code == 200, saved.text

    updated = client.post(cpath, json=make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=1, points=[[11, 20], [39, 20]],
    ))
    assert updated.status_code == 200, updated.text
    stale = client.get(apath, params=region_query(snapshot, review_id))
    assert stale.status_code == 200, stale.text
    assert stale.json()["latest"] is None
    assert stale.json()["history"][0]["current"] is False

    stale_write = {**assessment, "request_id": str(uuid.uuid4()), "expected_assessment_revision": 1}
    stale_response = client.post(apath, json=stale_write)
    assert stale_response.status_code == 409
    wrong_revision = client.post(cpath, json=make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[10, 20], [39, 20]],
    ))
    assert wrong_revision.status_code == 409


def test_newer_assignment_snapshot_stales_saved_region_assessment(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    caliper_response = client.post(
        measurement_path(study_id, image_id, region["region_id"]),
        json=make_caliper(snapshot, review_id, region["region_id"], lease,
                          revision=0, points=[[10, 20], [40, 20]]),
    )
    assert caliper_response.status_code == 200, caliper_response.text
    caliper = caliper_response.json()
    assessment_path_for_region = assessment_path(study_id, image_id, region["region_id"])
    assessment = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": caliper["diameter_mm"],
        },
        "patient_context": {},
        "source_caliper_event_id": caliper["request_id"],
        **lease,
    }
    saved = client.post(assessment_path_for_region, json=assessment)
    assert saved.status_code == 200, saved.text

    prior_ids = {row["region_id"] for row in snapshot["assignments"]}
    rotated = client.post(
        f"/api/cases/{study_id}/images/{image_id}/reviews/{review_id}/region-assignments",
        json={
            "request_id": str(uuid.uuid4()),
            "expected_revision": snapshot["review_revision"],
            "mask_sha256": candidates["mask_sha256"],
            "confirmed": True,
            "assignments": [
                {"component_index": row["component_index"], "previous_region_id": row["region_id"]}
                for row in snapshot["assignments"]
            ],
            "retired_region_ids": [],
            **lease,
        },
    )
    assert rotated.status_code == 200, rotated.text
    assert {row["region_id"] for row in rotated.json()["assignments"]} == prior_ids
    assert rotated.json()["assignment_request_id"] != snapshot["assignment_request_id"]

    latest_snapshot = client.get(
        f"/api/cases/{study_id}/images/{image_id}/region-assignments",
    )
    assert latest_snapshot.status_code == 200, latest_snapshot.text
    assert latest_snapshot.json()["assignment"]["assignment_request_id"] == rotated.json()["assignment_request_id"]
    assert latest_snapshot.json()["assignment"]["review_revision"] == snapshot["review_revision"] + 1
    current_assessment = client.get(
        assessment_path_for_region,
        params=region_query(snapshot, review_id),
    )
    assert current_assessment.status_code == 200, current_assessment.text
    assert current_assessment.json()["latest"] is None
    assert current_assessment.json()["history"][0]["current"] is False
    stale_write = {
        **assessment,
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 1,
    }
    assert client.post(assessment_path_for_region, json=stale_write).status_code == 409


def test_current_assessment_remains_readable_after_old_revision_history_cap(
    region_clinical_case, active_case_lease,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    caliper = client.post(
        measurement_path(study_id, image_id, region["region_id"]),
        json=make_caliper(snapshot, review_id, region["region_id"], lease,
                          revision=0, points=[[10, 20], [40, 20]]),
    )
    assert caliper.status_code == 200, caliper.text
    path = assessment_path(study_id, image_id, region["region_id"])
    payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": 3.0,
        },
        "patient_context": {},
        "source_caliper_event_id": caliper.json()["request_id"],
        **lease,
    }
    saved = client.post(path, json=payload)
    assert saved.status_code == 200, saved.text

    with Session(engine) as db:
        for _ in range(260):
            old_assignment_id = str(uuid.uuid4())
            db.add(RegionAssignmentBatchModel(
                request_id=old_assignment_id,
                study_id=study_id,
                image_id=image_id,
                review_id=review_id,
                actor_id="test-doctor",
                request_hash="a" * 64,
                review_revision=0,
                response_json={},
                created_at=datetime(2025, 1, 1),
            ))
            db.add(RegionCDSSAssessmentModel(
                request_id=str(uuid.uuid4()),
                assignment_request_id=old_assignment_id,
                study_id=study_id,
                image_id=image_id,
                review_id=review_id,
                region_id=region["region_id"],
                review_revision=0,
                mask_sha256=snapshot["mask_sha256"],
                assessment_revision=2,
                vision_findings_json={"assessment_source": "clinician"},
                patient_context_json={},
                source_caliper_event_id=None,
                source_caliper_revision=None,
                result_json={"status": "INSUFFICIENT_DATA"},
                actor_id="test-doctor",
                request_hash="b" * 64,
                created_at=datetime(2025, 1, 1),
            ))
            db.add(RegionCaliperEventModel(
                request_id=str(uuid.uuid4()),
                assignment_request_id=old_assignment_id,
                study_id=study_id,
                image_id=image_id,
                review_id=review_id,
                region_id=region["region_id"],
                review_revision=0,
                mask_sha256=snapshot["mask_sha256"],
                label="D1",
                measurement_revision=2,
                coordinate_space="decoded-source-image",
                points_json=[[10, 20], [40, 20]],
                source_width=512,
                source_height=512,
                diameter_px=30.0,
                diameter_mm=3.0,
                pixel_spacing_mm=0.1,
                calibration_source="MANUAL",
                calibration_hash="c" * 64,
                actor_id="test-doctor",
                request_hash="d" * 64,
                created_at=datetime(2025, 1, 1),
            ))
        db.commit()

    reloaded = client.get(path, params=region_query(snapshot, review_id))
    assert reloaded.status_code == 200, reloaded.text
    body = reloaded.json()
    assert body["latest_revision"] == 1
    assert body["latest"]["request_id"] == saved.json()["request_id"]
    assert body["latest"]["current"] is True
    assert body["history_truncated"] is True
    assert body["latest"]["source_caliper_event_id"] == caliper.json()["request_id"]
    assert len(body["history"]) == 100

    pages = [body]
    while pages[-1]["history_next_cursor"]:
        page = client.get(path, params={
            **region_query(snapshot, review_id),
            "cursor": pages[-1]["history_next_cursor"],
        })
        assert page.status_code == 200, page.text
        pages.append(page.json())
    history = [item for page in pages for item in page["history"]]
    history_ids = [item["request_id"] for item in history]
    assert len(history_ids) == 261
    assert len(set(history_ids)) == 261
    current_history_item = next(item for item in history if item["request_id"] == saved.json()["request_id"])
    assert current_history_item["current"] is True


def test_retiring_region_keeps_caliper_history_but_blocks_current_use(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    caliper_path = measurement_path(study_id, image_id, region["region_id"])
    saved = client.post(
        caliper_path,
        json=make_caliper(snapshot, review_id, region["region_id"], lease,
                          revision=0, points=[[10, 20], [40, 20]]),
    )
    assert saved.status_code == 200, saved.text
    assessment_path_for_region = assessment_path(study_id, image_id, region["region_id"])
    assessment_payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": 3.0,
        },
        "patient_context": {},
        **lease,
    }
    saved_assessment = client.post(assessment_path_for_region, json=assessment_payload)
    assert saved_assessment.status_code == 200, saved_assessment.text
    assert saved_assessment.json()["current"] is True

    assignments = [
        {
            "component_index": row["component_index"],
            **({"previous_region_id": row["region_id"]}
               if row["region_id"] != region["region_id"] else {}),
        }
        for row in snapshot["assignments"]
    ]
    rotated = client.post(
        f"/api/cases/{study_id}/images/{image_id}/reviews/{review_id}/region-assignments",
        json={
            "request_id": str(uuid.uuid4()),
            "expected_revision": snapshot["review_revision"],
            "mask_sha256": candidates["mask_sha256"],
            "confirmed": True,
            "assignments": assignments,
            "retired_region_ids": [region["region_id"]],
            **lease,
        },
    )
    assert rotated.status_code == 200, rotated.text
    assert region["region_id"] not in {row["region_id"] for row in rotated.json()["assignments"]}

    historical = client.get(caliper_path, params=region_query(snapshot, review_id))
    assert historical.status_code == 200, historical.text
    assert historical.json()["current"] is False
    assert historical.json()["measurements"]["D1"]["current"] is False
    assert historical.json()["measurements"]["D1"]["request_id"] == saved.json()["request_id"]
    historical_assessments = client.get(
        assessment_path_for_region,
        params=region_query(snapshot, review_id),
    )
    assert historical_assessments.status_code == 200, historical_assessments.text
    assert historical_assessments.json()["current"] is False
    assert historical_assessments.json()["latest"] is None
    assert historical_assessments.json()["history"][0]["current"] is False
    stale_assessment = {
        **assessment_payload,
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 1,
    }
    stale_assessment_response = client.post(
        assessment_path_for_region,
        json=stale_assessment,
    )
    assert stale_assessment_response.status_code == 409

    current_query = {
        **region_query(snapshot, review_id),
        "assignment_request_id": rotated.json()["assignment_request_id"],
    }
    missing_region = client.get(caliper_path, params=current_query)
    assert missing_region.status_code == 404
    stale_write = make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=1, points=[[11, 20], [39, 20]],
    )
    assert client.post(caliper_path, json=stale_write).status_code == 409


def test_unverified_calibration_never_produces_mm_and_new_review_stales_region(
    region_clinical_case, active_case_lease,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    with Session(engine) as db:
        image = db.get(ImageModel, image_id)
        image.calibration_source = "UNKNOWN"
        db.commit()
    base = measurement_path(study_id, image_id, region["region_id"])
    payload = make_caliper(snapshot, review_id, region["region_id"], lease,
                           revision=0, points=[[10, 20], [40, 20]])
    saved = client.post(base, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["diameter_px"] == 30
    assert saved.json()["diameter_mm"] is None
    assert saved.json()["usable_for_cdss"] is False

    with Session(engine) as db:
        db.add(ReviewModel(
            id=str(uuid.uuid4()), image_id=image_id, prediction_id=None,
            doctor_action="MODIFIED", verified_mask_rle=InferenceEngine.mask_to_rle(
                InferenceEngine.rle_to_mask(db.get(ReviewModel, review_id).verified_mask_rle)
            ),
        ))
        db.commit()
    stale_get = client.get(base, params=region_query(snapshot, review_id))
    assert stale_get.status_code == 200, stale_get.text
    assert stale_get.json()["current"] is False
    assert stale_get.json()["measurements"]["D1"]["current"] is False
    changed = make_caliper(snapshot, review_id, region["region_id"], lease,
                           revision=1, points=[[11, 20], [39, 20]])
    stale_write = client.post(base, json=changed)
    assert stale_write.status_code == 409


def test_caliper_commit_acknowledgement_loss_returns_complete_current_event(
    region_clinical_case, active_case_lease, monkeypatch,
):
    from sqlalchemy.exc import IntegrityError

    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    path = measurement_path(study_id, image_id, region["region_id"])
    payload = make_caliper(snapshot, review_id, region["region_id"], lease,
                           revision=0, points=[[10, 20], [40, 20]])
    original_commit = Session.commit
    injected = False

    def commit_then_lose_acknowledgement(db):
        nonlocal injected
        is_target_caliper = any(
            isinstance(row, RegionCaliperEventModel) and row.request_id == payload["request_id"]
            for row in db.new
        )
        original_commit(db)
        if is_target_caliper and not injected:
            injected = True
            raise IntegrityError("simulated commit acknowledgement loss", {}, RuntimeError("connection reset"))

    monkeypatch.setattr(Session, "commit", commit_then_lose_acknowledgement)
    response = client.post(path, json=payload)

    assert injected is True
    assert response.status_code == 200, response.text
    event = response.json()
    assert event["request_id"] == payload["request_id"]
    assert event["label"] == "D1"
    assert event["current"] is True
    assert event["calibration_current"] is True
    assert event["usable_for_cdss"] is True
    assert event["diameter_mm"] == 3


def test_caliper_save_response_is_stale_if_newer_revision_commits_before_response(
    region_clinical_case, active_case_lease, monkeypatch,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    path = measurement_path(study_id, image_id, region["region_id"])
    payload = make_caliper(snapshot, review_id, region["region_id"], lease,
                           revision=0, points=[[10, 20], [40, 20]])
    original_commit = Session.commit
    injected = False

    def commit_then_supersede_response(db):
        nonlocal injected
        target = next((
            row for row in db.new
            if isinstance(row, RegionCaliperEventModel) and row.request_id == payload["request_id"]
        ), None)
        original_commit(db)
        if target is None or injected:
            return

        injected = True
        with Session(engine) as competing_db:
            competing_db.add(RegionCaliperEventModel(
                request_id=str(uuid.uuid4()),
                assignment_request_id=target.assignment_request_id,
                study_id=target.study_id,
                image_id=target.image_id,
                review_id=target.review_id,
                region_id=target.region_id,
                review_revision=target.review_revision,
                mask_sha256=target.mask_sha256,
                label=target.label,
                measurement_revision=target.measurement_revision + 1,
                coordinate_space=target.coordinate_space,
                points_json=[[10.0, 21.0], [40.0, 21.0]],
                source_width=target.source_width,
                source_height=target.source_height,
                diameter_px=target.diameter_px,
                diameter_mm=target.diameter_mm,
                pixel_spacing_mm=target.pixel_spacing_mm,
                calibration_source=target.calibration_source,
                calibration_hash=target.calibration_hash,
                actor_id=target.actor_id,
                request_hash="f" * 64,
            ))
            original_commit(competing_db)

    monkeypatch.setattr(Session, "commit", commit_then_supersede_response)
    response = client.post(path, json=payload)

    assert injected is True
    assert response.status_code == 200, response.text
    event = response.json()
    assert event["measurement_revision"] == 1
    assert event["current"] is False
    assert event["usable_for_cdss"] is False
    latest = client.get(path, params=region_query(snapshot, review_id)).json()["measurements"]["D1"]
    assert latest["measurement_revision"] == 2


def test_caliper_ack_is_stale_when_review_changes_before_response(
    region_clinical_case, active_case_lease, monkeypatch,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    path = measurement_path(study_id, image_id, region["region_id"])
    payload = make_caliper(snapshot, review_id, region["region_id"], lease,
                           revision=0, points=[[10, 20], [40, 20]])
    original_commit = Session.commit
    injected = False

    def commit_then_save_new_review(db):
        nonlocal injected
        target = any(
            isinstance(row, RegionCaliperEventModel) and row.request_id == payload["request_id"]
            for row in db.new
        )
        original_commit(db)
        if target and not injected:
            injected = True
            with Session(engine) as competing_db:
                previous = competing_db.get(ReviewModel, review_id)
                competing_db.add(ReviewModel(
                    id=str(uuid.uuid4()),
                    image_id=image_id,
                    prediction_id=previous.prediction_id,
                    doctor_id="test-doctor",
                    doctor_action="MODIFIED",
                    verified_mask_rle=previous.verified_mask_rle,
                    created_at=datetime(2100, 1, 1),
                ))
                original_commit(competing_db)

    monkeypatch.setattr(Session, "commit", commit_then_save_new_review)
    response = client.post(path, json=payload)

    assert injected is True
    assert response.status_code == 200, response.text
    assert response.json()["current"] is False
    assert response.json()["usable_for_cdss"] is False
    assert response.json()["stale_reason"]


def test_assessment_commit_acknowledgement_loss_rechecks_staleness(
    region_clinical_case, active_case_lease, monkeypatch,
):
    from sqlalchemy.exc import IntegrityError

    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": 3.0,
        },
        "patient_context": {},
        **lease,
    }
    original_commit = Session.commit
    injected = False

    def commit_with_concurrent_new_review(db):
        nonlocal injected
        is_target_assessment = any(
            isinstance(row, RegionCDSSAssessmentModel) and row.request_id == payload["request_id"]
            for row in db.new
        )
        original_commit(db)
        if is_target_assessment and not injected:
            injected = True
            with Session(engine) as competing_db:
                prior_review = competing_db.get(ReviewModel, review_id)
                competing_db.add(ReviewModel(
                    id=str(uuid.uuid4()),
                    image_id=image_id,
                    prediction_id=prior_review.prediction_id,
                    doctor_id="test-doctor",
                    doctor_action="MODIFIED",
                    verified_mask_rle=prior_review.verified_mask_rle,
                    created_at=datetime(2100, 1, 1),
                ))
                original_commit(competing_db)
            raise IntegrityError("simulated commit acknowledgement loss", {}, RuntimeError("connection reset"))

    monkeypatch.setattr(Session, "commit", commit_with_concurrent_new_review)
    response = client.post(assessment_path(study_id, image_id, region["region_id"]), json=payload)

    assert injected is True
    assert response.status_code == 200, response.text
    assessment = response.json()
    assert assessment["request_id"] == payload["request_id"]
    assert assessment["status"] == "SAVED_RUO"
    assert assessment["replayed"] is True
    assert assessment["current"] is False
    assert assessment["stale_reason"]
    assert assessment["result"]


def test_assessment_ack_is_stale_when_review_changes_before_success_response(
    region_clinical_case, active_case_lease, monkeypatch,
):
    client, engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": 3.0,
        },
        "patient_context": {},
        **lease,
    }
    original_commit = Session.commit
    injected = False

    def commit_then_save_new_review(db):
        nonlocal injected
        target = any(
            isinstance(row, RegionCDSSAssessmentModel) and row.request_id == payload["request_id"]
            for row in db.new
        )
        original_commit(db)
        if target and not injected:
            injected = True
            with Session(engine) as competing_db:
                previous = competing_db.get(ReviewModel, review_id)
                competing_db.add(ReviewModel(
                    id=str(uuid.uuid4()),
                    image_id=image_id,
                    prediction_id=previous.prediction_id,
                    doctor_id="test-doctor",
                    doctor_action="MODIFIED",
                    verified_mask_rle=previous.verified_mask_rle,
                    created_at=datetime(2100, 1, 1),
                ))
                original_commit(competing_db)

    monkeypatch.setattr(Session, "commit", commit_then_save_new_review)
    response = client.post(
        assessment_path(study_id, image_id, region["region_id"]), json=payload,
    )

    assert injected is True
    assert response.status_code == 200, response.text
    assert response.json()["current"] is False
    assert response.json()["stale_reason"]


def test_concurrent_identical_caliper_request_is_idempotent_and_revision_conflict_is_safe(
    region_clinical_case, active_case_lease,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    path = measurement_path(study_id, image_id, region["region_id"])
    payload = make_caliper(snapshot, review_id, region["region_id"], lease,
                           revision=0, points=[[10, 20], [40, 20]])
    barrier = Barrier(2)

    def send_identical(_):
        barrier.wait(timeout=10)
        return client.post(path, json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(send_identical, range(2)))
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json()["request_id"] == second.json()["request_id"] == payload["request_id"]
    for response in (first, second):
        assert response.json()["current"] is True
        assert response.json()["calibration_current"] is True
        assert response.json()["usable_for_cdss"] is True

    race_barrier = Barrier(2)

    def send_competing(request_id, points):
        competing = make_caliper(snapshot, review_id, region["region_id"], lease,
                                 revision=1, points=points, request_id=request_id)
        race_barrier.wait(timeout=10)
        return client.post(path, json=competing)

    with ThreadPoolExecutor(max_workers=2) as pool:
        competing_responses = list(pool.map(
            lambda values: send_competing(*values),
            [(str(uuid.uuid4()), [[10, 21], [40, 21]]),
             (str(uuid.uuid4()), [[10, 22], [40, 22]])],
        ))
    assert sorted(response.status_code for response in competing_responses) == [200, 409]

    assessment_path_for_region = assessment_path(study_id, image_id, region["region_id"])
    assessment_payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {"assessment_source": "clinician", "modality": "ultrasound_2d",
                            "ultrasound_exam_complete": False},
        "patient_context": {},
        **lease,
    }
    assessment_barrier = Barrier(2)

    def send_identical_assessment(_):
        assessment_barrier.wait(timeout=10)
        return client.post(assessment_path_for_region, json=assessment_payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_assessment, second_assessment = list(pool.map(send_identical_assessment, range(2)))
    assert first_assessment.status_code == second_assessment.status_code == 200, (
        first_assessment.text, second_assessment.text,
    )
    assert first_assessment.json()["request_id"] == second_assessment.json()["request_id"]
    assert first_assessment.json()["assessment_revision"] == second_assessment.json()["assessment_revision"] == 1


def test_region_writes_fail_closed_without_lease_or_on_unconfirmed_descriptors(
    region_clinical_case, active_case_lease,
):
    from backend.app.routers.auth import get_current_user

    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    caliper_payload = make_caliper(
        snapshot, review_id, region["region_id"], lease,
        revision=0, points=[[10, 20], [40, 20]],
    )
    no_lease = {key: value for key, value in caliper_payload.items() if key not in {"lease_token", "page_instance_id"}}
    assert client.post(measurement_path(study_id, image_id, region["region_id"]), json=no_lease).status_code == 422

    assessment = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": False,
        "vision_findings": {},
        "patient_context": {},
        **lease,
    }
    assert client.post(assessment_path(study_id, image_id, region["region_id"]), json=assessment).status_code == 422

    unsupported = {**assessment, "confirmed": True,
                   "vision_findings": {"assessment_source": "clinician", "unknown_patient_diagnosis": "malignant"}}
    assert client.post(assessment_path(study_id, image_id, region["region_id"]), json=unsupported).status_code == 422

    original = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = lambda: UserModel(id="tech", username="tech", role="TECHNICIAN")
    try:
        assert client.post(measurement_path(study_id, image_id, region["region_id"]), json=caliper_payload).status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = original


def test_region_caliper_huge_integer_coordinate_returns_validation_error_not_server_error(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    payload = make_caliper(
        snapshot,
        review_id,
        region["region_id"],
        lease,
        revision=0,
        points=[[10, 20], [10**400, 20]],
    )

    with TestClient(app, raise_server_exceptions=False) as safe_client:
        response = safe_client.post(
            measurement_path(study_id, image_id, region["region_id"]),
            json=payload,
        )

    assert response.status_code == 422, response.text


def test_region_cdss_huge_caliper_descriptor_returns_validation_error_not_server_error(
    region_clinical_case, active_case_lease,
):
    client, _engine, study_id, image_id, review_id = region_clinical_case
    _candidates, snapshot, region, lease = confirm_regions(
        client, active_case_lease, study_id, image_id, review_id,
    )
    caliper = client.post(
        measurement_path(study_id, image_id, region["region_id"]),
        json=make_caliper(
            snapshot, review_id, region["region_id"], lease,
            revision=0, points=[[10, 20], [40, 20]],
        ),
    )
    assert caliper.status_code == 200, caliper.text

    payload = {
        "request_id": str(uuid.uuid4()),
        "expected_assessment_revision": 0,
        "assignment_request_id": snapshot["assignment_request_id"],
        "review_id": review_id,
        "region_id": region["region_id"],
        "mask_sha256": snapshot["mask_sha256"],
        "confirmed": True,
        "vision_findings": {
            "assessment_source": "clinician",
            "modality": "ultrasound_2d",
            "ultrasound_exam_complete": False,
            "max_diameter_mm": 10**400,
        },
        "patient_context": {},
        "source_caliper_event_id": caliper.json()["request_id"],
        **lease,
    }
    with TestClient(app, raise_server_exceptions=False) as safe_client:
        response = safe_client.post(
            assessment_path(study_id, image_id, region["region_id"]),
            json=payload,
        )

    assert response.status_code == 422, response.text
