import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.db.database import SessionLocal, StudyModel, ImageModel


@pytest.mark.usefixtures('doctor_access')
@pytest.mark.parametrize('image', [np.zeros((256,256,3),dtype=np.uint8), np.full((256,256,3),255,dtype=np.uint8)])
def test_unsuitable_intake_image_rejected_without_creating_case(image):
    with SessionLocal() as db:
        before = (db.query(StudyModel).count(), db.query(ImageModel).count())
    ok, content = cv2.imencode('.png', image)
    assert ok
    with TestClient(app) as client:
        response = client.post('/api/intake/extract-metadata?validate_quality=true', files={'file':('synthetic.png',content.tobytes(),'image/png')})
    assert response.status_code == 422, response.text
    assert isinstance(response.json()['detail'], str)
    with SessionLocal() as db:
        assert (db.query(StudyModel).count(), db.query(ImageModel).count()) == before
