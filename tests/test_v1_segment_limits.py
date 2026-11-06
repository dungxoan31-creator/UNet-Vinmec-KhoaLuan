"""The v1 segment upload must enforce encoded and decoded size limits."""

import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.routers import v1_endpoints


def _call_segment(contents):
    upload = UploadFile(filename="image.png", file=BytesIO(contents))
    return asyncio.run(v1_endpoints.segment_image_v1(file=upload, db=None))


def test_v1_segment_rejects_oversized_upload_before_decode(monkeypatch):
    monkeypatch.setattr(
        v1_endpoints.cv2,
        "imdecode",
        lambda *_args: (_ for _ in ()).throw(AssertionError("decode must not run")),
    )

    with pytest.raises(HTTPException) as error:
        _call_segment(b"x" * (20 * 1024 * 1024 + 1))

    assert error.value.status_code == 413


def test_v1_segment_rejects_oversized_dimensions_before_decode(monkeypatch):
    class ImageHeader:
        size = (5001, 5000)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(Image, "open", lambda _source: ImageHeader())
    monkeypatch.setattr(
        v1_endpoints.cv2,
        "imdecode",
        lambda *_args: (_ for _ in ()).throw(AssertionError("decode must not run")),
    )

    with pytest.raises(HTTPException) as error:
        _call_segment(b"x" * 64)

    assert error.value.status_code == 413


def test_v1_segment_rejects_upload_and_sample_id_as_ambiguous(monkeypatch):
    monkeypatch.setattr(
        v1_endpoints.model_registry,
        "get_primary_adapter",
        lambda: (_ for _ in ()).throw(AssertionError("model lookup must not run")),
    )
    upload = UploadFile(filename="image.png", file=BytesIO(b"unused"))

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            v1_endpoints.segment_image_v1(
                file=upload,
                image_id="sample_untrusted",
                db=None,
            )
        )

    assert error.value.status_code == 422


def test_v1_segment_http_rejects_upload_and_image_id_as_ambiguous(doctor_access):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/segment?image_id=sample_untrusted",
            files={"file": ("image.png", b"unused", "image/png")},
        )

    assert response.status_code == 422


@pytest.mark.parametrize("image_id", [None, "", " ", "\t"])
def test_v1_segment_rejects_missing_or_blank_source_before_model_lookup(monkeypatch, image_id):
    monkeypatch.setattr(
        v1_endpoints.model_registry,
        "get_primary_adapter",
        lambda: (_ for _ in ()).throw(AssertionError("model lookup must not run")),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(v1_endpoints.segment_image_v1(file=None, image_id=image_id, db=None))

    assert error.value.status_code == 400
