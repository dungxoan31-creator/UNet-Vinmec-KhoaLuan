"""Only a single-frame ultrasound DICOM may enter the 2D model workflow."""

from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, get_db

pytestmark = pytest.mark.usefixtures("doctor_access")


def make_dicom(modality: str, frames: int = 1, spacing: tuple[float, float] = (0.25, 0.25)) -> bytes:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dcm = FileDataset("test.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    dcm.SOPClassUID = meta.MediaStorageSOPClassUID
    dcm.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dcm.Modality = modality
    dcm.StudyInstanceUID = generate_uid()
    dcm.SeriesInstanceUID = generate_uid()
    dcm.Rows = 16
    dcm.Columns = 16
    dcm.PixelSpacing = list(spacing)
    dcm.SamplesPerPixel = 1
    dcm.PhotometricInterpretation = "MONOCHROME2"
    dcm.BitsAllocated = 8
    dcm.BitsStored = 8
    dcm.HighBit = 7
    dcm.PixelRepresentation = 0
    if frames > 1:
        dcm.NumberOfFrames = frames
    dcm.PixelData = np.full((frames, 16, 16), 100, dtype=np.uint8).tobytes()
    buffer = BytesIO()
    dcm.save_as(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("modality", "frames", "expected"),
    [("US", 1, 200), ("MR", 1, 400), ("CT", 1, 400), ("OT", 1, 400), ("US", 2, 400)],
)
def test_upload_rejects_dicom_outside_2d_ultrasound_scope(tmp_path, monkeypatch, modality, frames, expected):
    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(f"sqlite:///{tmp_path / 'dicom.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/upload", files={"file": ("test.dcm", make_dicom(modality, frames), "application/dicom")}
            )
        assert response.status_code == expected, response.text
        if expected == 400:
            assert "siêu âm 2D" in response.json()["detail"]
            assert not list(tmp_path.glob("*.dcm"))
        else:
            metadata = response.json()["dicom_metadata"]
            assert metadata["modality"] == "US"
            assert metadata["number_of_frames"] == 1
            assert metadata["study_instance_uid"]
            assert metadata["series_instance_uid"]
            assert metadata["calibrated_spacing_mm"] == 0.25
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_existing_non_ultrasound_dicom_is_not_decoded_for_inference(tmp_path):
    from backend.app.routers.inference import decode_ultrasound_image

    file_path = tmp_path / "old_mr.dcm"
    file_path.write_bytes(make_dicom("MR"))
    assert decode_ultrasound_image(str(file_path), grayscale=True) is None


def test_anisotropic_dicom_spacing_is_not_reduced_to_one_scalar(tmp_path):
    from backend.app.routers.inference import extract_dicom_calibration_spacing

    file_path = tmp_path / "anisotropic.dcm"
    file_path.write_bytes(make_dicom("US", spacing=(0.25, 0.5)))
    assert extract_dicom_calibration_spacing(str(file_path)) is None
