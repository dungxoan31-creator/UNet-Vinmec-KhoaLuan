"""Only a single-frame ultrasound DICOM may enter the 2D model workflow."""

from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, get_db

pytestmark = pytest.mark.usefixtures("doctor_access")


def make_dicom(
    modality: str,
    frames: int = 1,
    spacing: tuple[float, float] = (0.25, 0.25),
    include_pixel_data: bool = True,
    declare_frame_count: bool = True,
    frame_count_override: int | None = None,
) -> bytes:
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
    if frames > 1 and declare_frame_count:
        dcm.NumberOfFrames = frame_count_override or frames
    if include_pixel_data:
        dcm.PixelData = np.full((frames, 16, 16), 100, dtype=np.uint8).tobytes()
    buffer = BytesIO()
    dcm.save_as(buffer)
    return buffer.getvalue()


def test_replacement_uids_keep_case_and_laterality_links_without_source_uids():
    import pydicom

    from backend.services.dicom_privacy import minimize_dicom_patient_metadata

    right_a = pydicom.dcmread(BytesIO(make_dicom("US")))
    right_b = pydicom.dcmread(BytesIO(make_dicom("US")))
    left = pydicom.dcmread(BytesIO(make_dicom("US")))
    source_uids = {
        str(right_a.StudyInstanceUID),
        str(right_a.SeriesInstanceUID),
        str(right_a.SOPInstanceUID),
    }

    minimize_dicom_patient_metadata(
        right_a, study_key="case-1", series_key="case-1:R", instance_key="image-1"
    )
    minimize_dicom_patient_metadata(
        right_b, study_key="case-1", series_key="case-1:R", instance_key="image-2"
    )
    minimize_dicom_patient_metadata(
        left, study_key="case-1", series_key="case-1:L", instance_key="image-3"
    )

    assert right_a.StudyInstanceUID == right_b.StudyInstanceUID == left.StudyInstanceUID
    assert right_a.SeriesInstanceUID == right_b.SeriesInstanceUID
    assert right_a.SeriesInstanceUID != left.SeriesInstanceUID
    assert len({right_a.SOPInstanceUID, right_b.SOPInstanceUID, left.SOPInstanceUID}) == 3
    assert not source_uids.intersection(
        {str(right_a.StudyInstanceUID), str(right_a.SeriesInstanceUID), str(right_a.SOPInstanceUID)}
    )
    assert all(
        dataset.file_meta.MediaStorageSOPInstanceUID == dataset.SOPInstanceUID
        for dataset in (right_a, right_b, left)
    )


def test_upload_minimizes_patient_tags_and_private_data_without_changing_pixels_or_spacing(
    tmp_path, monkeypatch
):
    import pydicom

    from backend.app.main import app
    from backend.app.routers import inference
    from backend.db.database import ImageModel

    source = pydicom.dcmread(BytesIO(make_dicom("US")))
    source.PatientName = "SYNTHETIC^PATIENT_SENTINEL"
    source.PatientID = "SYNTHETIC-PID-SENTINEL"
    source.PatientAddress = "SYNTHETIC-ADDRESS-SENTINEL"
    source.PatientAge = "045Y"
    source.PatientSex = "F"
    source.InstitutionName = "SYNTHETIC-INSTITUTION-SENTINEL"
    source.InstitutionAddress = "SYNTHETIC-INSTITUTION-ADDRESS-SENTINEL"
    source.InstitutionalDepartmentName = "SYNTHETIC-DEPARTMENT-SENTINEL"
    source.StationName = "STN-SYNTH-01"
    source.ReferringPhysicianName = "SYNTHETIC^PHYSICIAN_SENTINEL"
    source.OperatorsName = "SYNTHETIC^OPERATOR_SENTINEL"
    source.AccessionNumber = "ACC-SYNTH-01"
    source.StudyDescription = "SYNTHETIC-STUDY-DESCRIPTION-SENTINEL"
    source.StudyDate = "20261021"
    source.StudyTime = "101112"
    source.BurnedInAnnotation = "YES"
    source.file_meta.SourceApplicationEntityTitle = "US-ROOM-01"
    source.file_meta.ImplementationClassUID = generate_uid()
    source.file_meta.ImplementationVersionName = "SRC-IMPL-01"
    source.FrameOfReferenceUID = generate_uid()
    source.PatientIdentityRemoved = "YES"
    original_uids = {
        keyword: getattr(source, keyword)
        for keyword in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "FrameOfReferenceUID")
    }
    source.add_new(0x00111010, "LO", "PRIVATE-SENTINEL")
    nested = Dataset()
    nested.add_new(0x00111010, "LO", "NESTED-PRIVATE-SENTINEL")
    source.ReferencedPerformedProcedureStepSequence = Sequence([nested])
    original_pixels = source.PixelData
    payload = BytesIO()
    source.save_as(payload)

    engine = create_engine(f"sqlite:///{tmp_path / 'dicom-privacy.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/upload",
                files={"file": ("patient.dcm", payload.getvalue(), "application/dicom")},
            )

        assert response.status_code == 200, response.text
        response_data = response.json()
        with Session(engine) as db:
            record = db.get(ImageModel, response_data["image_id"])
            stored = pydicom.dcmread(record.raw_path)

        assert "PatientName" not in stored
        assert "PatientID" not in stored
        assert "PatientAddress" not in stored
        for keyword in (
            "PatientAge",
            "PatientSex",
            "InstitutionName",
            "InstitutionAddress",
            "InstitutionalDepartmentName",
            "StationName",
            "ReferringPhysicianName",
            "OperatorsName",
            "AccessionNumber",
            "StudyDescription",
            "StudyDate",
            "StudyTime",
        ):
            assert keyword not in stored
        for keyword, original_uid in original_uids.items():
            assert str(getattr(stored, keyword)) != str(original_uid)
        assert stored.file_meta.MediaStorageSOPInstanceUID == stored.SOPInstanceUID
        from pydicom.uid import PYDICOM_IMPLEMENTATION_UID

        assert stored.file_meta.ImplementationClassUID == PYDICOM_IMPLEMENTATION_UID
        assert "SourceApplicationEntityTitle" not in stored.file_meta
        assert "ImplementationVersionName" not in stored.file_meta
        assert "ReferencedPerformedProcedureStepSequence" not in stored
        assert stored.PatientIdentityRemoved == "NO"
        assert stored.BurnedInAnnotation == "YES"
        assert stored.LongitudinalTemporalInformationModified == "REMOVED"
        assert 0x00111010 not in stored
        assert stored.PixelData == original_pixels
        assert stored.PixelSpacing == [0.25, 0.25]
        assert response_data["dicom_metadata"]["privacy_processing"] == {
            "status": "partial_metadata_minimization",
            "pixel_data_reviewed": False,
            "burned_in_annotation": "YES",
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


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
            assert set(metadata) == {
                "modality",
                "number_of_frames",
                "privacy_processing",
                "calibrated_spacing_mm",
            }
            assert metadata["privacy_processing"] == {
                "status": "partial_metadata_minimization",
                "pixel_data_reviewed": False,
                "burned_in_annotation": "UNKNOWN",
            }
            assert metadata["calibrated_spacing_mm"] == 0.25
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_existing_non_ultrasound_dicom_is_not_decoded_for_inference(tmp_path):
    from backend.app.routers.inference import decode_ultrasound_image

    file_path = tmp_path / "old_mr.dcm"
    file_path.write_bytes(make_dicom("MR"))
    assert decode_ultrasound_image(str(file_path), grayscale=True) is None


@pytest.mark.parametrize("samples_per_pixel", [2, 255])
def test_unsupported_dicom_sample_count_is_rejected_before_pixel_decode(
    tmp_path, monkeypatch, samples_per_pixel
):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    file_path = tmp_path / "invalid-samples.dcm"
    file_path.write_bytes(b"mocked DICOM reader")
    pixel_array_accessed = []

    class FakeDicom:
        Rows = 16
        Columns = 16
        SamplesPerPixel = samples_per_pixel
        PhotometricInterpretation = "MONOCHROME2"

        @staticmethod
        def get(key, default=None):
            return {"Modality": "US", "NumberOfFrames": 1}.get(key, default)

        @property
        def pixel_array(self):
            pixel_array_accessed.append(True)
            return np.zeros((16, 16, 2), dtype=np.uint8)

    monkeypatch.setattr(pydicom, "dcmread", lambda _path: FakeDicom())

    assert decode_ultrasound_image(str(file_path)) is None
    assert pixel_array_accessed == []


@pytest.mark.parametrize("bits_allocated", [12, 65535])
def test_unsupported_dicom_bit_depth_is_rejected_before_pixel_decode(
    tmp_path, monkeypatch, bits_allocated
):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    file_path = tmp_path / "invalid-bit-depth.dcm"
    file_path.write_bytes(b"mocked DICOM reader")
    pixel_array_accessed = []

    class FakeDicom:
        Rows = 16
        Columns = 16
        SamplesPerPixel = 1
        BitsAllocated = bits_allocated
        PhotometricInterpretation = "MONOCHROME2"

        @staticmethod
        def get(key, default=None):
            return {"Modality": "US", "NumberOfFrames": 1}.get(key, default)

        @property
        def pixel_array(self):
            pixel_array_accessed.append(True)
            return np.zeros((16, 16), dtype=np.uint8)

    monkeypatch.setattr(pydicom, "dcmread", lambda _path: FakeDicom())

    assert decode_ultrasound_image(str(file_path)) is None
    assert pixel_array_accessed == []


def test_dicom_photometric_interpretation_must_match_sample_count_before_decode(
    tmp_path, monkeypatch
):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    file_path = tmp_path / "invalid-photometric-samples.dcm"
    file_path.write_bytes(b"mocked DICOM reader")
    pixel_array_accessed = []

    class FakeDicom:
        Rows = 16
        Columns = 16
        SamplesPerPixel = 3
        BitsAllocated = 8
        PhotometricInterpretation = "MONOCHROME2"

        @staticmethod
        def get(key, default=None):
            return {"Modality": "US", "NumberOfFrames": 1}.get(key, default)

        @property
        def pixel_array(self):
            pixel_array_accessed.append(True)
            return np.zeros((16, 16, 3), dtype=np.uint8)

    monkeypatch.setattr(pydicom, "dcmread", lambda _path: FakeDicom())

    assert decode_ultrasound_image(str(file_path)) is None
    assert pixel_array_accessed == []


def test_monochrome1_pixels_are_inverted_for_grayscale_display(tmp_path):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    source_pixels = np.array([[0, 64], [128, 255]], dtype=np.uint8)
    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    dicom.Rows, dicom.Columns = source_pixels.shape
    dicom.PhotometricInterpretation = "MONOCHROME1"
    dicom.PixelData = source_pixels.tobytes()
    file_path = tmp_path / "monochrome1.dcm"
    dicom.save_as(file_path)

    decoded = decode_ultrasound_image(str(file_path), grayscale=True)

    assert decoded.dtype == np.uint8
    assert np.array_equal(decoded, 255 - source_pixels)


@pytest.mark.parametrize(
    ("headers",),
    [
        ({"PhotometricInterpretation": "RGB", "SamplesPerPixel": 3, "BitsAllocated": 16,
          "BitsStored": 16, "HighBit": 15, "PlanarConfiguration": 0},),
        ({"BitsStored": 7},),
        ({"HighBit": 6},),
        ({"PixelRepresentation": 1},),
        ({"SamplesPerPixel": None},),
        ({"SamplesPerPixel": 1.5},),
        ({"PhotometricInterpretation": "RGB", "SamplesPerPixel": 3,
          "PlanarConfiguration": None},),
        ({"PhotometricInterpretation": "RGB", "SamplesPerPixel": 3,
          "PlanarConfiguration": 2},),
    ],
)
def test_invalid_dicom_pixel_module_header_is_rejected_before_pixel_decode(
    tmp_path, monkeypatch, headers
):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    pixel_array_accessed = []

    class FakeDicom:
        Rows = 16
        Columns = 16
        SamplesPerPixel = 1
        PhotometricInterpretation = "MONOCHROME2"
        BitsAllocated = 8
        BitsStored = 8
        HighBit = 7
        PixelRepresentation = 0
        PlanarConfiguration = None

        @staticmethod
        def get(key, default=None):
            return {"Modality": "US", "NumberOfFrames": 1}.get(key, default)

        @property
        def pixel_array(self):
            pixel_array_accessed.append(True)
            return np.zeros((16, 16), dtype=np.uint8)

    for key, value in headers.items():
        if value is None:
            monkeypatch.delattr(FakeDicom, key)
        else:
            monkeypatch.setattr(FakeDicom, key, value)

    file_path = tmp_path / "invalid-pixel-module.dcm"
    file_path.write_bytes(b"mocked DICOM reader")
    monkeypatch.setattr(pydicom, "dcmread", lambda _path: FakeDicom())

    assert decode_ultrasound_image(str(file_path)) is None
    assert pixel_array_accessed == []


@pytest.mark.parametrize(
    ("declare_frame_count", "frame_count_override"),
    [(False, None), (True, 1)],
)
def test_dicom_with_excess_pixel_frames_and_incorrect_frame_count_is_rejected(
    tmp_path, declare_frame_count, frame_count_override
):
    from backend.services.image_service import decode_ultrasound_image

    file_path = tmp_path / "undeclared-multiframe.dcm"
    file_path.write_bytes(
        make_dicom(
            "US",
            frames=2,
            declare_frame_count=declare_frame_count,
            frame_count_override=frame_count_override,
        )
    )

    with pytest.warns(UserWarning, match="sufficient to contain 2 frames"):
        assert decode_ultrasound_image(str(file_path), grayscale=True) is None


def test_upload_rejects_dicom_with_missing_pixel_data_and_removes_temp_file(tmp_path, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import inference

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))

    with TestClient(app) as client:
        response = client.post(
            "/api/upload",
            files={
                "file": (
                    "missing-pixels.dcm",
                    make_dicom("US", include_pixel_data=False),
                    "application/dicom",
                )
            },
        )

    assert response.status_code == 400
    assert "File có thể bị hỏng" in response.json()["detail"]
    assert list(upload_dir.iterdir()) == []


def test_anisotropic_dicom_spacing_is_not_reduced_to_one_scalar(tmp_path):
    from backend.app.routers.inference import extract_dicom_calibration_spacing

    file_path = tmp_path / "anisotropic.dcm"
    file_path.write_bytes(make_dicom("US", spacing=(0.25, 0.5)))
    assert extract_dicom_calibration_spacing(str(file_path)) is None


def test_image_service_owns_shared_dicom_decode_and_spacing_validation(tmp_path):
    from backend.services.image_service import (
        decode_ultrasound_image,
        extract_dicom_calibration_spacing,
        validate_pixel_spacing,
    )

    file_path = tmp_path / "shared-service.dcm"
    file_path.write_bytes(make_dicom("US", spacing=(0.25, 0.25)))

    assert decode_ultrasound_image(str(file_path), grayscale=True).shape == (16, 16)
    assert extract_dicom_calibration_spacing(str(file_path)) == 0.25
    with pytest.raises(ValueError, match="finite"):
        validate_pixel_spacing(float("nan"))


def test_dicom_without_pixel_spacing_decodes_without_claiming_physical_scale(tmp_path):
    import pydicom

    from backend.services.image_service import (
        decode_ultrasound_image,
        extract_dicom_calibration_spacing,
    )

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    del dicom.PixelSpacing
    file_path = tmp_path / "missing-pixel-spacing.dcm"
    dicom.save_as(file_path)

    decoded = decode_ultrasound_image(str(file_path), grayscale=True)

    assert decoded is not None
    assert decoded.shape == (16, 16)
    assert extract_dicom_calibration_spacing(str(file_path)) is None


@pytest.mark.parametrize("spacing", [1e-5, 1e150])
def test_dicom_pixel_spacing_outside_safe_measurement_range_is_unset(
    tmp_path, spacing
):
    import pydicom

    from backend.services.image_service import extract_dicom_calibration_spacing

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    dicom.PixelSpacing = [spacing, spacing]
    file_path = tmp_path / "unsafe-pixel-spacing.dcm"
    dicom.save_as(file_path)

    assert extract_dicom_calibration_spacing(str(file_path)) is None


@pytest.mark.parametrize("delta_cm", [1e-6, 1e150])
def test_dicom_region_spacing_outside_safe_measurement_range_is_unset(
    tmp_path, delta_cm
):
    import pydicom
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence

    from backend.services.image_service import extract_dicom_calibration_spacing

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    region = Dataset()
    region.RegionSpatialFormat = 1
    region.PhysicalUnitsXDirection = 3
    region.PhysicalUnitsYDirection = 3
    region.PhysicalDeltaX = delta_cm
    region.PhysicalDeltaY = delta_cm
    region.RegionLocationMinX0 = region.RegionLocationMinY0 = 0
    region.RegionLocationMaxX1 = region.RegionLocationMaxY1 = 15
    dicom.SequenceOfUltrasoundRegions = Sequence([region])
    file_path = tmp_path / "unsafe-region-spacing.dcm"
    dicom.save_as(file_path)

    assert extract_dicom_calibration_spacing(str(file_path)) is None


def test_palette_color_dicom_applies_palette_luts_before_returning_pixels(tmp_path):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    dicom.PhotometricInterpretation = "PALETTE COLOR"
    dicom.RedPaletteColorLookupTableDescriptor = [4, 0, 8]
    dicom.GreenPaletteColorLookupTableDescriptor = [4, 0, 8]
    dicom.BluePaletteColorLookupTableDescriptor = [4, 0, 8]
    for tag in ((0x0028, 0x1101), (0x0028, 0x1102), (0x0028, 0x1103)):
        dicom[tag].VR = "US"
    dicom.RedPaletteColorLookupTableData = bytes([0, 255, 0, 0])
    dicom.GreenPaletteColorLookupTableData = bytes([0, 0, 255, 0])
    dicom.BluePaletteColorLookupTableData = bytes([255, 0, 0, 0])
    pixels = np.zeros((16, 16), dtype=np.uint8)
    pixels[0, :3] = [0, 1, 2]
    dicom.PixelData = pixels.tobytes()

    file_path = tmp_path / "palette-color.dcm"
    dicom.save_as(file_path)

    decoded = decode_ultrasound_image(str(file_path))
    grayscale = decode_ultrasound_image(str(file_path), grayscale=True)

    assert decoded.shape == (16, 16, 3)
    assert decoded[0, :3].tolist() == [[255, 0, 0], [0, 0, 255], [0, 255, 0]]
    assert grayscale[0, :3].tolist() == [29, 76, 150]


def test_palette_color_dicom_without_luts_is_rejected(tmp_path):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    dicom.PhotometricInterpretation = "PALETTE COLOR"
    file_path = tmp_path / "palette-no-lut.dcm"
    dicom.save_as(file_path)

    assert decode_ultrasound_image(str(file_path)) is None


def test_palette_color_16bit_lut_is_scaled_to_display_range(tmp_path):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    dicom.PhotometricInterpretation = "PALETTE COLOR"
    dicom.RedPaletteColorLookupTableDescriptor = [4, 0, 16]
    dicom.GreenPaletteColorLookupTableDescriptor = [4, 0, 16]
    dicom.BluePaletteColorLookupTableDescriptor = [4, 0, 16]
    for tag in ((0x0028, 0x1101), (0x0028, 0x1102), (0x0028, 0x1103)):
        dicom[tag].VR = "US"
    dicom.RedPaletteColorLookupTableData = np.array([0, 65535, 0, 0], dtype="<u2").tobytes()
    dicom.GreenPaletteColorLookupTableData = np.array([0, 0, 65535, 0], dtype="<u2").tobytes()
    dicom.BluePaletteColorLookupTableData = np.array([65535, 0, 0, 0], dtype="<u2").tobytes()
    dicom.BitsAllocated = dicom.BitsStored = 16
    dicom.HighBit = 15
    pixels = np.zeros((16, 16), dtype=np.uint16)
    pixels[0, :3] = [0, 1, 2]
    dicom.PixelData = pixels.tobytes()

    file_path = tmp_path / "palette-color-16bit.dcm"
    dicom.save_as(file_path)

    decoded = decode_ultrasound_image(str(file_path))

    assert decoded.dtype == np.uint8
    assert decoded[0, :3].tolist() == [[255, 0, 0], [0, 0, 255], [0, 255, 0]]


def test_ybr_full_dicom_uses_opencv_bgr_channel_order(tmp_path):
    import pydicom
    from pydicom.pixels import convert_color_space

    from backend.services.image_service import decode_ultrasound_image

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    dicom.SamplesPerPixel = 3
    dicom.PhotometricInterpretation = "YBR_FULL"
    dicom.PlanarConfiguration = 0
    rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    rgb[0, :3] = [[0, 0, 255], [255, 0, 0], [0, 255, 0]]
    dicom.PixelData = convert_color_space(rgb, "RGB", "YBR_FULL").tobytes()

    file_path = tmp_path / "ybr-full.dcm"
    dicom.save_as(file_path)

    decoded = decode_ultrasound_image(str(file_path))

    assert decoded.shape == (16, 16, 3)
    expected_bgr = rgb[0, :3, ::-1]
    assert np.max(np.abs(decoded[0, :3].astype(int) - expected_bgr.astype(int))) <= 2


def test_legacy_pydicom_ybr_full_pixels_are_converted_to_opencv_bgr(
    tmp_path, monkeypatch
):
    import pydicom
    from pydicom.pixels import convert_color_space

    from backend.services.image_service import decode_ultrasound_image

    rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    rgb[0, :3] = [[0, 0, 255], [255, 0, 0], [0, 255, 0]]
    ybr = convert_color_space(rgb, "RGB", "YBR_FULL")
    pixel_array_accessed = []

    class LegacyDicom:
        Rows = 16
        Columns = 16
        SamplesPerPixel = 3
        PhotometricInterpretation = "YBR_FULL"
        BitsAllocated = 8
        BitsStored = 8
        HighBit = 7
        PixelRepresentation = 0
        PlanarConfiguration = 0

        @staticmethod
        def get(key, default=None):
            return {"Modality": "US", "NumberOfFrames": 1}.get(key, default)

        @property
        def pixel_array(self):
            pixel_array_accessed.append(True)
            return ybr

    file_path = tmp_path / "legacy-ybr-full.dcm"
    file_path.write_bytes(b"legacy DICOM test double")
    monkeypatch.setattr(pydicom, "dcmread", lambda _path: LegacyDicom())

    decoded = decode_ultrasound_image(str(file_path))

    assert pixel_array_accessed == [True]
    assert decoded.shape == (16, 16, 3)
    expected_bgr = rgb[0, :3, ::-1]
    assert np.max(np.abs(decoded[0, :3].astype(int) - expected_bgr.astype(int))) <= 2


@pytest.mark.parametrize("photometric", ["YBR_RCT", "YBR_ICT", "YBR_PARTIAL_420"])
def test_unverified_ybr_transfer_colors_are_rejected_before_pixel_decode(
    tmp_path, monkeypatch, photometric
):
    import pydicom

    from backend.services.image_service import decode_ultrasound_image

    pixel_array_accessed = []

    class UnsupportedYbrDicom:
        Rows = 16
        Columns = 16
        SamplesPerPixel = 3
        PhotometricInterpretation = photometric
        BitsAllocated = 8

        @staticmethod
        def get(key, default=None):
            return {"Modality": "US", "NumberOfFrames": 1}.get(key, default)

        @property
        def pixel_array(self):
            pixel_array_accessed.append(True)
            return np.zeros((16, 16, 3), dtype=np.uint8)

    file_path = tmp_path / "unsupported-ybr.dcm"
    file_path.write_bytes(b"unsupported YBR test double")
    monkeypatch.setattr(pydicom, "dcmread", lambda _path: UnsupportedYbrDicom())

    assert decode_ultrasound_image(str(file_path)) is None
    assert pixel_array_accessed == []


@pytest.mark.parametrize("spacing", [0, -0.25, float("inf"), True, "0.25"])
def test_image_service_rejects_nonphysical_pixel_spacing_values(spacing):
    from backend.services.image_service import validate_pixel_spacing

    with pytest.raises(ValueError):
        validate_pixel_spacing(spacing)


def test_spectral_doppler_time_axis_is_not_used_as_image_spacing(tmp_path):
    import pydicom

    from backend.services.image_service import extract_dicom_calibration_spacing

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    region = Dataset()
    region.RegionSpatialFormat = 3  # Spectral Doppler
    region.RegionDataType = 3  # Pulsed wave Doppler
    region.RegionFlags = 0
    region.PhysicalUnitsXDirection = 4  # seconds
    region.PhysicalUnitsYDirection = 7  # cm/sec
    region.PhysicalDeltaX = 0.05
    region.PhysicalDeltaY = -0.05
    region.RegionLocationMinX0 = region.RegionLocationMinY0 = 0
    region.RegionLocationMaxX1 = region.RegionLocationMaxY1 = 15
    dicom.SequenceOfUltrasoundRegions = Sequence([region])

    file_path = tmp_path / "spectral-doppler.dcm"
    dicom.save_as(file_path)

    assert extract_dicom_calibration_spacing(str(file_path)) is None


@pytest.mark.parametrize("bounds", [None, (2, 2, 13, 13)])
def test_ultrasound_region_spacing_is_not_applied_outside_its_declared_bounds(tmp_path, bounds):
    import pydicom
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence

    from backend.services.image_service import extract_dicom_calibration_spacing

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    region = Dataset()
    region.RegionSpatialFormat = 1
    region.PhysicalUnitsXDirection = 3
    region.PhysicalUnitsYDirection = 3
    region.PhysicalDeltaX = 0.025
    region.PhysicalDeltaY = 0.025
    if bounds is not None:
        (
            region.RegionLocationMinX0,
            region.RegionLocationMinY0,
            region.RegionLocationMaxX1,
            region.RegionLocationMaxY1,
        ) = bounds
    dicom.SequenceOfUltrasoundRegions = Sequence([region])

    file_path = tmp_path / "partial-region.dcm"
    dicom.save_as(file_path)

    assert extract_dicom_calibration_spacing(str(file_path)) is None


def test_ultrasound_region_spacing_is_ambiguous_when_multiple_regions_exist(tmp_path):
    import pydicom
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence

    from backend.services.image_service import extract_dicom_calibration_spacing

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    tissue = Dataset()
    tissue.RegionSpatialFormat = 1
    tissue.PhysicalUnitsXDirection = 3
    tissue.PhysicalUnitsYDirection = 3
    tissue.PhysicalDeltaX = 0.025
    tissue.PhysicalDeltaY = 0.025
    tissue.RegionLocationMinX0 = tissue.RegionLocationMinY0 = 0
    tissue.RegionLocationMaxX1 = tissue.RegionLocationMaxY1 = 15

    time_region = Dataset()
    time_region.RegionSpatialFormat = 2
    time_region.PhysicalUnitsXDirection = 4
    time_region.PhysicalUnitsYDirection = 4
    time_region.PhysicalDeltaX = 0.05
    time_region.PhysicalDeltaY = 0.05
    time_region.RegionLocationMinX0 = time_region.RegionLocationMinY0 = 0
    time_region.RegionLocationMaxX1 = time_region.RegionLocationMaxY1 = 15
    dicom.SequenceOfUltrasoundRegions = Sequence([tissue, time_region])

    file_path = tmp_path / "multiple-regions.dcm"
    dicom.save_as(file_path)

    assert extract_dicom_calibration_spacing(str(file_path)) is None


def test_single_full_frame_spatial_region_provides_isotropic_spacing(tmp_path):
    import pydicom
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence

    from backend.services.image_service import extract_dicom_calibration_spacing

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    region = Dataset()
    region.RegionSpatialFormat = 1
    region.PhysicalUnitsXDirection = 3
    region.PhysicalUnitsYDirection = 3
    region.PhysicalDeltaX = 0.025
    region.PhysicalDeltaY = 0.025
    region.RegionLocationMinX0 = region.RegionLocationMinY0 = 0
    region.RegionLocationMaxX1 = region.RegionLocationMaxY1 = 15
    dicom.SequenceOfUltrasoundRegions = Sequence([region])

    file_path = tmp_path / "full-frame-region.dcm"
    dicom.save_as(file_path)

    assert extract_dicom_calibration_spacing(str(file_path)) == 0.25


@pytest.mark.parametrize(
    "calibration_case",
    ["partial_region", "missing_pixel_spacing", "tiny_pixel_spacing", "large_pixel_spacing"],
)
def test_upload_keeps_unverified_dicom_calibration_unset(
    tmp_path, monkeypatch, calibration_case
):
    import pydicom
    from pydicom.dataset import Dataset
    from pydicom.sequence import Sequence

    from backend.app.main import app
    from backend.app.routers import inference
    from backend.db.database import ImageModel

    dicom = pydicom.dcmread(BytesIO(make_dicom("US")))
    if calibration_case == "partial_region":
        region = Dataset()
        region.RegionSpatialFormat = 1
        region.PhysicalUnitsXDirection = 3
        region.PhysicalUnitsYDirection = 3
        region.PhysicalDeltaX = 0.025
        region.PhysicalDeltaY = 0.025
        region.RegionLocationMinX0 = region.RegionLocationMinY0 = 2
        region.RegionLocationMaxX1 = region.RegionLocationMaxY1 = 13
        dicom.SequenceOfUltrasoundRegions = Sequence([region])
    elif calibration_case == "missing_pixel_spacing":
        del dicom.PixelSpacing
    elif calibration_case == "tiny_pixel_spacing":
        dicom.PixelSpacing = [1e-5, 1e-5]
    else:
        dicom.PixelSpacing = [1e150, 1e150]
    buffer = BytesIO()
    dicom.save_as(buffer)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'partial-region-upload.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_dir))

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/upload",
                files={
                    "file": (
                        f"{calibration_case}.dcm",
                        buffer.getvalue(),
                        "application/dicom",
                    )
                },
            )

        assert response.status_code == 200, response.text
        assert response.json()["dicom_metadata"]["calibrated_spacing_mm"] is None

        with Session(engine) as db:
            image = db.get(ImageModel, response.json()["image_id"])
            assert image.pixel_spacing_mm is None
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
