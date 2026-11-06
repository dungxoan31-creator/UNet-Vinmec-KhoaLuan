"""Read-only component candidates for an immutable reviewed mask."""
import uuid

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
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.services.inference_engine import InferenceEngine

pytestmark = pytest.mark.usefixtures("doctor_access")


@pytest.fixture
def region_case(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'regions.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    mask = np.zeros((512, 512), dtype=np.uint8)
    cv2.rectangle(mask, (10, 20), (40, 50), 1, -1)
    cv2.rectangle(mask, (200, 300), (204, 304), 1, -1)
    rle = InferenceEngine.mask_to_rle(mask)
    with Session(engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.add(PatientModel(id="p", anonymized_pid="SYN-REGION"))
        db.add(StudyModel(id="s", patient_id="p", study_date="2026-10-28"))
        db.add(StudyModel(id="other", patient_id="p", study_date="2026-10-28"))
        db.add(ImageModel(id="image", study_id="s", filename="synthetic.png", raw_path="unused.png", laterality="L"))
        db.add(PredictionModel(id="prediction", image_id="image", raw_mask_rle=rle, measurements={}))
        db.add(ReviewModel(id="review", image_id="image", prediction_id="prediction", doctor_action="ACCEPTED_RAW", verified_mask_rle=rle))
        db.commit()
    def temporary_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_lists_all_regions_including_small_without_creating_identity(region_case):
    client, _engine = region_case
    response = client.get("/api/cases/s/images/image/reviews/review/region-candidates")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["review_id"] == "review"
    assert result["requires_clinician_confirmation"] is True
    assert result["coordinate_space"] == "letterbox-512"
    assert result["algorithm"] == "opencv-connected-components-8-v1"
    assert len(result["mask_sha256"]) == 64
    assert sorted(item["pixel_count"] for item in result["components"]) == [25, 961]
    assert all("lesion_id" not in item for item in result["components"])


def test_rejects_cross_study_or_image_reference(region_case):
    client, _engine = region_case
    for path in (
        "/api/cases/other/images/image/reviews/review/region-candidates",
        "/api/cases/s/images/missing/reviews/review/region-candidates",
        "/api/cases/s/images/image/reviews/missing/region-candidates",
    ):
        assert client.get(path).status_code == 404


def test_full_mask_and_empty_mask_have_valid_candidate_counts():
    from backend.services.lesion_reconciliation import review_component_candidates
    full = review_component_candidates(np.ones((512, 512), dtype=np.uint8))
    assert full["components"][0]["seed_xy"] == [0, 0]
    assert full["components"][0]["pixel_count"] == 512 * 512
    assert review_component_candidates(np.zeros((512, 512), dtype=np.uint8))["components"] == []


def test_corrupt_stored_review_mask_fails_closed(region_case):
    client, engine = region_case
    with Session(engine) as db:
        review = db.get(ReviewModel, "review")
        review.verified_mask_rle = {"shape": [512, 512], "first_val": 0, "counts": [3]}
        db.commit()
    response = client.get("/api/cases/s/images/image/reviews/review/region-candidates")
    assert response.status_code == 422


def test_excess_components_fail_closed():
    from backend.services.lesion_reconciliation import review_component_candidates
    mask = np.zeros((512, 512), dtype=np.uint8)
    for i in range(129):
        mask[(i // 20) * 3, (i % 20) * 3] = 1
    with pytest.raises(ValueError, match="Too many"):
        review_component_candidates(mask)


def test_candidates_require_authentication(region_case):
    from backend.app.routers.auth import get_current_user
    client, _engine = region_case
    original = app.dependency_overrides.pop(get_current_user)
    try:
        response = client.get("/api/cases/s/images/image/reviews/review/region-candidates")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = original


def test_region_confirmation_is_atomic_and_idempotent(region_case, active_case_lease):
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    candidates = client.get(base + "/region-candidates").json()
    lease = active_case_lease(client, "s")
    request_id = str(uuid.uuid4())
    payload = {"request_id": request_id, "expected_revision": 0, "mask_sha256": candidates["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}], **lease}
    first = client.post(base + "/region-assignments", json=payload)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["review_revision"] == 1
    assert len({row["region_id"] for row in result["assignments"]}) == 2
    second = client.post(base + "/region-assignments", json=payload)
    assert second.status_code == 200 and second.json() == result
    changed = {**payload, "assignments": [{"component_index": 1}]}
    assert client.post(base + "/region-assignments", json=changed).status_code == 409
    with Session(engine) as db:
        assert db.get(StudyModel, "s").review_revision == 1


def test_region_confirmation_rejects_missing_component_and_stale_mask(region_case, active_case_lease):
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    candidates = client.get(base + "/region-candidates").json()
    lease = active_case_lease(client, "s")
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "mask_sha256": candidates["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}], **lease}
    assert client.post(base + "/region-assignments", json=payload).status_code == 422
    payload["assignments"] = [{"component_index": 1}, {"component_index": 2}]
    payload["mask_sha256"] = "a" * 64
    assert client.post(base + "/region-assignments", json=payload).status_code == 409
    with Session(engine) as db:
        assert db.get(StudyModel, "s").review_revision == 0


def test_region_confirmation_requires_lease_confirmation_and_current_revision(region_case, active_case_lease):
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    digest = client.get(base + "/region-candidates").json()["mask_sha256"]
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "mask_sha256": digest,
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}]}
    assert client.post(base + "/region-assignments", json=payload).status_code == 423
    payload.update(active_case_lease(client, "s"))
    payload["confirmed"] = False
    assert client.post(base + "/region-assignments", json=payload).status_code == 422
    payload["confirmed"] = True
    payload["expected_revision"] = 1
    assert client.post(base + "/region-assignments", json=payload).status_code == 409
    with Session(engine) as db:
        assert db.get(StudyModel, "s").review_revision == 0


def test_region_identity_cannot_be_duplicated_or_invented(region_case, active_case_lease):
    client, _engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    digest = client.get(base + "/region-candidates").json()["mask_sha256"]
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "mask_sha256": digest,
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    first = client.post(base + "/region-assignments", json=payload)
    assert first.status_code == 200, first.text
    region_id = first.json()["assignments"][0]["region_id"]
    payload.update(request_id=str(uuid.uuid4()), expected_revision=1,
                   assignments=[{"component_index": 1, "previous_region_id": region_id},
                                {"component_index": 2, "previous_region_id": region_id}])
    assert client.post(base + "/region-assignments", json=payload).status_code == 422
    payload["assignments"][1]["previous_region_id"] = str(uuid.uuid4())
    assert client.post(base + "/region-assignments", json=payload).status_code == 422
    del payload["assignments"][1]["previous_region_id"]
    payload["retired_region_ids"] = [first.json()["assignments"][1]["region_id"]]
    response = client.post(base + "/region-assignments", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["assignments"][0]["region_id"] == region_id


def test_latest_assignment_marks_old_review_as_stale(region_case, active_case_lease):
    client, engine = region_case
    path = "/api/cases/s/images/image/region-assignments"
    assert client.get(path).json() == {"assignment": None, "stale": False}
    base = "/api/cases/s/images/image/reviews/review"
    digest = client.get(base + "/region-candidates").json()["mask_sha256"]
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "mask_sha256": digest,
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    assert client.post(base + "/region-assignments", json=payload).status_code == 200
    assert client.get(path).json()["stale"] is False
    with Session(engine) as db:
        old = db.get(ReviewModel, "review")
        from datetime import timedelta
        db.add(ReviewModel(id="review-new", image_id="image", prediction_id="prediction",
                           doctor_action="ACCEPTED_RAW", verified_mask_rle=old.verified_mask_rle,
                           created_at=old.created_at + timedelta(seconds=1)))
        db.commit()
    assert client.get(path).json()["stale"] is True
    payload.update(request_id=str(uuid.uuid4()), expected_revision=1)
    assert client.post(base + "/region-assignments", json=payload).status_code == 409
    assert client.get("/api/cases/other/images/image/region-assignments").status_code == 404


def test_deleting_review_cascades_assignment_batch(region_case, active_case_lease):
    from backend.db.database import RegionAssignmentBatchModel
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    digest = client.get(base + "/region-candidates").json()["mask_sha256"]
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "mask_sha256": digest,
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    assert client.post(base + "/region-assignments", json=payload).status_code == 200
    with Session(engine) as db:
        db.query(ReviewModel).filter_by(id="review").delete()
        db.commit()
        assert db.query(RegionAssignmentBatchModel).count() == 0


def test_previous_region_id_cannot_cross_images(region_case, active_case_lease):
    client, engine = region_case
    lease = active_case_lease(client, "s")
    base = "/api/cases/s/images/image/reviews/review"
    digest = client.get(base + "/region-candidates").json()["mask_sha256"]
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "mask_sha256": digest,
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}], **lease}
    region_id = client.post(base + "/region-assignments", json=payload).json()["assignments"][0]["region_id"]
    with Session(engine) as db:
        rle = db.get(ReviewModel, "review").verified_mask_rle
        db.add(ImageModel(id="image-2", study_id="s", filename="synthetic-2.png", raw_path="unused-2.png"))
        db.add(ReviewModel(id="review-2", image_id="image-2", doctor_action="ACCEPTED_RAW", verified_mask_rle=rle))
        db.commit()
    payload.update(request_id=str(uuid.uuid4()), expected_revision=1,
                   assignments=[{"component_index": 1, "previous_region_id": region_id}, {"component_index": 2}])
    other_base = "/api/cases/s/images/image-2/reviews/review-2"
    assert client.post(other_base + "/region-assignments", json=payload).status_code == 422


def test_concurrent_identical_confirmation_is_idempotent(region_case, active_case_lease):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    digest = client.get(base + "/region-candidates").json()["mask_sha256"]
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0, "mask_sha256": digest,
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    barrier = Barrier(2)
    def send():
        barrier.wait(timeout=10)
        return client.post(base + "/region-assignments", json=payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: send(), range(2)))
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json() == second.json()
    with Session(engine) as db:
        assert db.get(StudyModel, "s").review_revision == 1


def test_confirm_denies_non_doctor_and_finalized_study(region_case, active_case_lease):
    from backend.app.routers.auth import get_current_user
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0,
               "mask_sha256": client.get(base + "/region-candidates").json()["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    original = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = lambda: UserModel(id="tech", username="tech", role="TECHNICIAN")
    try:
        assert client.post(base + "/region-assignments", json=payload).status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = original
    with Session(engine) as db:
        db.get(StudyModel, "s").status = "LOCKED"
        db.commit()
    assert client.post(base + "/region-assignments", json=payload).status_code == 409


def test_proposals_detect_split_without_automatic_identity_transfer(region_case, active_case_lease):
    from datetime import timedelta
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0,
               "mask_sha256": client.get(base + "/region-candidates").json()["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    confirmed = client.post(base + "/region-assignments", json=payload).json()
    old_id = confirmed["assignments"][0]["region_id"]
    with Session(engine) as db:
        old = db.get(ReviewModel, "review")
        mask = InferenceEngine.rle_to_mask(old.verified_mask_rle)
        mask[20:51, 25] = 0
        db.add(ReviewModel(id="review-split", image_id="image", prediction_id="prediction",
                           doctor_action="MODIFIED", verified_mask_rle=InferenceEngine.mask_to_rle(mask),
                           created_at=old.created_at + timedelta(seconds=1)))
        db.commit()
    path = "/api/cases/s/images/image/reviews/review-split/region-proposals"
    response = client.get(path)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["requires_clinician_confirmation"] is True
    assert len(data["ambiguous"]) == 2
    assert all(item["previous_ids"] == [old_id] for item in data["ambiguous"])
    assert len(data["unambiguous"]) == 1
    assert client.get("/api/cases/s/images/image/region-assignments").json()["stale"] is True


def test_proposals_reject_unversioned_or_tampered_snapshot(region_case, active_case_lease):
    from backend.db.database import RegionAssignmentBatchModel
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0,
               "mask_sha256": client.get(base + "/region-candidates").json()["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    first = client.post(base + "/region-assignments", json=payload)
    assert first.status_code == 200
    original_id = first.json()["assignments"][0]["region_id"]
    with Session(engine) as db:
        batch = db.get(RegionAssignmentBatchModel, payload["request_id"])
        saved = dict(batch.response_json)
        saved.pop("algorithm", None)
        batch.response_json = saved
        db.commit()
    assert client.get(base + "/region-proposals").status_code == 409
    assert client.get("/api/cases/s/images/image/region-assignments").status_code == 409
    payload.update(request_id=str(uuid.uuid4()), expected_revision=1,
                   assignments=[{"component_index": 1, "previous_region_id": original_id},
                                {"component_index": 2}])
    assert client.post(base + "/region-assignments", json=payload).status_code == 409


def test_confirmation_requires_explicit_retirement_of_unmatched_previous_region(region_case, active_case_lease):
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0,
               "mask_sha256": client.get(base + "/region-candidates").json()["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    first = client.post(base + "/region-assignments", json=payload)
    assert first.status_code == 200
    first_id, second_id = [row["region_id"] for row in first.json()["assignments"]]
    payload.update(request_id=str(uuid.uuid4()), expected_revision=1,
                   assignments=[{"component_index": 1, "previous_region_id": first_id}, {"component_index": 2}])
    assert client.post(base + "/region-assignments", json=payload).status_code == 422
    with Session(engine) as db:
        assert db.get(StudyModel, "s").review_revision == 1
    payload["retired_region_ids"] = [second_id]
    second = client.post(base + "/region-assignments", json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["retired_region_ids"] == [second_id]


def test_proposals_without_snapshot_and_cross_scope(region_case):
    client, engine = region_case
    path = "/api/cases/s/images/image/reviews/review/region-proposals"
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.json()["new_components"] == [1, 2]
    assert response.json()["previous_review_id"] is None
    assert client.get("/api/cases/other/images/image/reviews/review/region-proposals").status_code == 404
    with Session(engine) as db:
        assert db.get(StudyModel, "s").review_revision == 0


def test_proposals_reject_changed_previous_mask(region_case, active_case_lease):
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0,
               "mask_sha256": client.get(base + "/region-candidates").json()["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    assert client.post(base + "/region-assignments", json=payload).status_code == 200
    with Session(engine) as db:
        review = db.get(ReviewModel, "review")
        mask = InferenceEngine.rle_to_mask(review.verified_mask_rle)
        mask[20, 10] = 0
        review.verified_mask_rle = InferenceEngine.mask_to_rle(mask)
        db.commit()
    assert client.get(base + "/region-proposals").status_code == 409


@pytest.mark.parametrize("field", ["study_id", "image_id", "review_id", "review_revision"])
def test_assignment_snapshot_rejects_corrupt_scope(region_case, active_case_lease, field):
    from backend.db.database import RegionAssignmentBatchModel
    client, engine = region_case
    base = "/api/cases/s/images/image/reviews/review"
    payload = {"request_id": str(uuid.uuid4()), "expected_revision": 0,
               "mask_sha256": client.get(base + "/region-candidates").json()["mask_sha256"],
               "confirmed": True, "assignments": [{"component_index": 1}, {"component_index": 2}],
               **active_case_lease(client, "s")}
    assert client.post(base + "/region-assignments", json=payload).status_code == 200
    with Session(engine) as db:
        batch = db.get(RegionAssignmentBatchModel, payload["request_id"])
        batch.response_json = {**batch.response_json, field: 999 if field == "review_revision" else "wrong"}
        db.commit()
    assert client.get(base + "/region-proposals").status_code == 409
