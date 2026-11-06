"""Validate synthetic browser fixtures without reading any source patient data."""

import hashlib

import cv2
import numpy as np
from pydicom import dcmread

from scripts.generate_synthetic_e2e_fixtures import generate_fixtures


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generator_outputs_valid_deterministic_synthetic_formats_and_fault_cases(tmp_path):
    first = generate_fixtures(tmp_path / "first", seed=42)
    second = generate_fixtures(tmp_path / "second", seed=42)

    for name in ("synthetic_left.png", "synthetic_right.png", "synthetic_left.jpg"):
        image = cv2.imread(str(first / name), cv2.IMREAD_GRAYSCALE)
        assert image is not None
        assert image.shape == (512, 512)
    letterbox = cv2.imread(str(first / "synthetic_letterbox_640x480.png"), cv2.IMREAD_GRAYSCALE)
    assert letterbox is not None
    assert letterbox.shape == (480, 640)
    assert _sha256(first / "synthetic_left.png") == _sha256(second / "synthetic_left.png")
    assert _sha256(first / "synthetic_right.png") == _sha256(second / "synthetic_right.png")
    assert _sha256(first / "synthetic_letterbox_640x480.png") == _sha256(second / "synthetic_letterbox_640x480.png")
    assert _sha256(first / "synthetic_ovary.dcm") == _sha256(second / "synthetic_ovary.dcm")

    dicom = dcmread(first / "synthetic_ovary.dcm")
    assert dicom.PatientID == "000000001"
    assert dicom.PatientName == "SYNTHETIC^TEST"
    assert dicom.PatientAge == "034Y"
    assert dicom.Modality == "US"
    assert dicom.BurnedInAnnotation == "NO"
    assert dicom.NumberOfFrames == 1
    assert dicom.SOPInstanceUID == dicom.file_meta.MediaStorageSOPInstanceUID
    assert dicom.PixelSpacing == [0.1, 0.1]
    assert np.asarray(dicom.pixel_array).shape == (512, 512)

    assert (first / "fake_corrupted.png").read_text(encoding="utf-8").startswith("This is an invalid")
    assert (first / "empty_zero_byte.png").stat().st_size == 0
    assert (first / "oversized_26mb.png").stat().st_size > 25 * 1024 * 1024
