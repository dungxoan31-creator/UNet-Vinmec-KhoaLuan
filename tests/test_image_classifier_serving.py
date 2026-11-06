import cv2
import numpy as np
import torch

from backend.services.image_classifier import ResearchImageClassifier, classification_tensor, CHECKSUM
from ai_training.train_classifier_8class import MMOTUClassificationDataset


def test_classification_preprocessing_matches_training(tmp_path):
    image = np.random.default_rng(42).integers(0, 256, (180, 320, 3), dtype=np.uint8)
    path = tmp_path / 'synthetic.png'
    cv2.imwrite(str(path), image)
    dataset = MMOTUClassificationDataset([{'image_path': str(path), 'label': 0, 'image_id': 'synthetic'}], image_size=256)
    assert torch.equal(classification_tensor(image)[0], dataset[0]['image'])


def test_real_checkpoint_predicts_finite_eight_class_distribution():
    result = ResearchImageClassifier().predict(np.full((128, 192, 3), 80, dtype=np.uint8))
    assert result['status'] in {'PREDICTED', 'ABSTAIN'}, result
    assert len(result['probabilities']) == 8
    assert abs(sum(result['probabilities'].values()) - 1) < 1e-5
    assert result['provenance']['checkpoint_sha256'] == CHECKSUM
    assert result['requires_clinician_confirmation'] is True


def test_missing_checkpoint_returns_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr('backend.services.image_classifier.CHECKPOINT', tmp_path / 'missing.pth')
    assert ResearchImageClassifier().predict(np.zeros((32,32), dtype=np.uint8))['status'] == 'UNAVAILABLE'


def test_wrong_checksum_is_rejected(monkeypatch):
    monkeypatch.setattr('backend.services.image_classifier.CHECKSUM', '0' * 64)
    assert ResearchImageClassifier().predict(np.zeros((32,32), dtype=np.uint8))['status'] == 'UNAVAILABLE'


def test_prediction_api_persists_classification_and_case_reopens_it(doctor_access, active_case_lease, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.config import model_registry
    from backend.app.main import app
    from backend.db.database import SessionLocal, PredictionModel
    from tests.helpers.fixture_factory import create_test_study, create_test_image
    from tests.helpers.synthetic_inference import enable_synthetic_inference

    enable_synthetic_inference(monkeypatch, model_registry)
    path = tmp_path / 'synthetic.png'
    cv2.imwrite(str(path), np.random.default_rng(5).integers(20,180,(256,320),dtype=np.uint8))
    with SessionLocal() as db:
        study = create_test_study(db, facility_id='FAC-DEFAULT-TEST')
        image = create_test_image(db, study.id, raw_path=str(path))
        study_id, image_id = study.id, image.id
    with TestClient(app) as client:
        lease = active_case_lease(client, study_id)
        response = client.post('/api/predict/'+image_id, headers={
            'X-Case-Lease-Token': lease['lease_token'],
            'X-Case-Page-Instance-Id': lease['page_instance_id'],
        })
        assert response.status_code == 200, response.text
        result = response.json()
        classification = result['ai_diagnosis']
        assert classification['status'] in {'PREDICTED','ABSTAIN'}, classification
        with SessionLocal() as db:
            saved = db.get(PredictionModel, result['prediction_id'])
            assert saved.response_extras_json['ai_diagnosis'] == classification
        reopened = client.get('/api/cases/'+study_id)
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()['images'][0]['prediction']['ai_diagnosis'] == classification
