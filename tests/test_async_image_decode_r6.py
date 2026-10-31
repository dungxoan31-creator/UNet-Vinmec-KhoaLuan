"""Tests for Task 8: R6 (P2) — Offload CPU-bound image decoding to threadpool."""

from io import BytesIO
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool as starlette_run_in_threadpool

from backend.app.main import app
from backend.app.routers import inference
from backend.db.database import Base, ImageModel, get_db

pytestmark = pytest.mark.usefixtures("doctor_access")


def make_test_dicom(
    modality: str = "US",
    rows: int = 16,
    columns: int = 16,
) -> bytes:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dcm = FileDataset("test.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    dcm.SOPClassUID = meta.MediaStorageSOPClassUID
    dcm.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dcm.Modality = modality
    dcm.BurnedInAnnotation = "NO"
    dcm.StudyInstanceUID = generate_uid()
    dcm.SeriesInstanceUID = generate_uid()
    dcm.Rows = rows
    dcm.Columns = columns
    dcm.PixelSpacing = [0.25, 0.25]
    dcm.SamplesPerPixel = 1
    dcm.PhotometricInterpretation = "MONOCHROME2"
    dcm.BitsAllocated = 8
    dcm.BitsStored = 8
    dcm.HighBit = 7
    dcm.PixelRepresentation = 0
    dcm.NumberOfFrames = 1
    dcm.PixelData = np.full((1, rows, columns), 100, dtype=np.uint8).tobytes()
    buf = BytesIO()
    dcm.save_as(buf)
    return buf.getvalue()


def make_test_png(w: int = 64, h: int = 64) -> bytes:
    img = np.full((h, w, 3), 128, dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def test_extract_intake_metadata_offloads_cpu_bound_png(monkeypatch):
    """Verify that extract_intake_metadata offloads CPU-bound decoding and analysis for raster images."""
    assert hasattr(inference, "run_in_threadpool"), "inference router must import run_in_threadpool"
    monkeypatch.setattr(inference, "SYNTHETIC_DEMO_MODE", False)

    called_functions = []

    async def tracking_threadpool(func, *args, **kwargs):
        name = getattr(func, "__name__", str(func))
        called_functions.append(name)
        return await starlette_run_in_threadpool(func, *args, **kwargs)

    monkeypatch.setattr(inference, "run_in_threadpool", tracking_threadpool)

    png_bytes = make_test_png(64, 64)
    with TestClient(app) as client:
        resp = client.post(
            "/api/intake/extract-metadata",
            files={"file": ("VNMC_TEST_LEFT.png", png_bytes, "image/png")},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "metadata" in data
    assert "calibration" in data

    assert "extract_file_metadata" in called_functions
    assert "decode_ultrasound_image" in called_functions
    assert "get_automatic_calibration" in called_functions


def test_extract_intake_metadata_offloads_cpu_bound_dicom(monkeypatch):
    """Verify that extract_intake_metadata offloads DICOM parsing, decoding, and analysis."""
    assert hasattr(inference, "run_in_threadpool"), "inference router must import run_in_threadpool"
    monkeypatch.setattr(inference, "SYNTHETIC_DEMO_MODE", False)

    called_functions = []

    async def tracking_threadpool(func, *args, **kwargs):
        name = getattr(func, "__name__", str(func))
        called_functions.append(name)
        return await starlette_run_in_threadpool(func, *args, **kwargs)

    monkeypatch.setattr(inference, "run_in_threadpool", tracking_threadpool)

    dcm_bytes = make_test_dicom()
    with TestClient(app) as client:
        resp = client.post(
            "/api/intake/extract-metadata",
            files={"file": ("patient_scan.dcm", dcm_bytes, "application/dicom")},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "metadata" in data
    assert "calibration" in data

    assert "dcmread" in called_functions
    assert "extract_file_metadata" in called_functions
    assert "decode_ultrasound_image" in called_functions
    assert "get_automatic_calibration" in called_functions


def test_upload_image_offloads_cpu_bound_png(tmp_path, monkeypatch):
    """Verify that upload_image offloads preflight raster checks and decoding for PNG uploads."""
    assert hasattr(inference, "run_in_threadpool"), "inference router must import run_in_threadpool"
    monkeypatch.setattr(inference, "SYNTHETIC_DEMO_MODE", False)

    called_functions = []

    async def tracking_threadpool(func, *args, **kwargs):
        name = getattr(func, "__name__", str(func))
        called_functions.append(name)
        return await starlette_run_in_threadpool(func, *args, **kwargs)

    monkeypatch.setattr(inference, "run_in_threadpool", tracking_threadpool)

    engine = create_engine(f"sqlite:///{tmp_path / 'upload-async.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        png_bytes = make_test_png(80, 80)
        with TestClient(app) as client:
            resp = client.post(
                "/api/upload",
                files={"file": ("us_scan.png", png_bytes, "image/png")},
            )

        assert resp.status_code == 200, resp.text
        assert "_preflight_raster_dimensions" in called_functions
        assert "decode_ultrasound_image" in called_functions
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_upload_image_offloads_cpu_bound_dicom(tmp_path, monkeypatch):
    """Verify that upload_image offloads DICOM read, minimization, save, and decode."""
    assert hasattr(inference, "run_in_threadpool"), "inference router must import run_in_threadpool"
    monkeypatch.setattr(inference, "SYNTHETIC_DEMO_MODE", False)

    called_functions = []

    async def tracking_threadpool(func, *args, **kwargs):
        name = getattr(func, "__name__", str(func))
        called_functions.append(name)
        return await starlette_run_in_threadpool(func, *args, **kwargs)

    monkeypatch.setattr(inference, "run_in_threadpool", tracking_threadpool)

    engine = create_engine(f"sqlite:///{tmp_path / 'upload-async-dicom.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        dcm_bytes = make_test_dicom()
        with TestClient(app) as client:
            resp = client.post(
                "/api/upload",
                files={"file": ("patient_scan.dcm", dcm_bytes, "application/dicom")},
            )

        assert resp.status_code == 200, resp.text
        assert "dcmread" in called_functions
        assert "minimize_dicom_patient_metadata" in called_functions
        assert "save_as" in called_functions
        assert "decode_ultrasound_image" in called_functions
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
