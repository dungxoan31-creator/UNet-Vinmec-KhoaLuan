"""
Generates artificial, synthetic ultrasound-like fixtures for Playwright E2E testing.
These fixtures contain no source patient images. Their synthetic nature does not
certify HIPAA, GDPR, or any other regulatory compliance.
Creates:
1. synthetic_left.png (512x512 synthetic ultrasound)
2. synthetic_right.png (512x512 synthetic ultrasound)
3. synthetic_letterbox_640x480.png (640x480 synthetic ultrasound for non-square Canvas review)
4. synthetic_color_doppler_640x480.png (color patch for decoded-source viewer tests)
5. synthetic_bilateral.dcm (valid DICOM with PixelSpacing)
6. fake_corrupted.png (invalid text pretending to be png)
7. empty_zero_byte.png (0-byte file)
8. oversized_26mb.png (> 25MB file to test 413 limit)
"""

import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "artifacts" / "synthetic_fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def generate_fixtures(fixtures_dir: Path | str | None = None, seed: int = 20261025) -> Path:
    """Generate deterministic synthetic-only browser fixtures in a caller-selected directory."""
    output_dir = Path(fixtures_dir) if fixtures_dir is not None else FIXTURES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthetic 512x512 ultrasound-like images with a fan field and cyst-like shapes.
    rng = np.random.default_rng(seed)
    xx, yy = np.meshgrid(np.arange(512), np.arange(512))
    distance = np.hypot(xx - 256, yy - 50)
    fan = (distance > 100) & (distance < 450)
    gray_l = np.zeros((512, 512), dtype=np.uint8)
    gray_r = np.zeros((512, 512), dtype=np.uint8)
    gray_l[fan] = rng.integers(15, 65, size=int(fan.sum()), dtype=np.uint8)
    gray_r[fan] = rng.integers(15, 65, size=int(fan.sum()), dtype=np.uint8)
    img_l = cv2.cvtColor(gray_l, cv2.COLOR_GRAY2BGR)
    img_r = cv2.cvtColor(gray_r, cv2.COLOR_GRAY2BGR)

    # Ovary 1 (Left): cyst centered at (220, 260) with radius 45
    cv2.circle(img_l, (220, 260), 45, (10, 10, 10), -1)
    cv2.circle(img_l, (220, 260), 48, (180, 180, 180), 2)  # Wall

    # Ovary 2 (Right): cyst centered at (280, 270) with radius 55
    cv2.circle(img_r, (280, 270), 55, (12, 12, 12), -1)
    cv2.circle(img_r, (280, 270), 58, (170, 170, 170), 2)

    left_path = output_dir / "synthetic_left.png"
    right_path = output_dir / "synthetic_right.png"
    left_jpg_path = output_dir / "synthetic_left.jpg"
    letterbox_path = output_dir / "synthetic_letterbox_640x480.png"
    color_doppler_path = output_dir / "synthetic_color_doppler_640x480.png"
    if not cv2.imwrite(str(left_path), img_l) or not cv2.imwrite(str(right_path), img_r):
        raise OSError("Could not write synthetic PNG fixtures.")
    if not cv2.imwrite(str(left_jpg_path), img_l, [cv2.IMWRITE_JPEG_QUALITY, 90]):
        raise OSError("Could not write synthetic JPEG fixture.")
    # A non-square fixture exposes 512x512 letterbox padding and source/model alignment in Canvas tests.
    letterbox_x, letterbox_y = np.meshgrid(np.arange(640), np.arange(480))
    letterbox_distance = np.hypot(letterbox_x - 320, letterbox_y - 48)
    letterbox_fan = (letterbox_distance > 100) & (letterbox_distance < 480)
    letterbox_gray = np.zeros((480, 640), dtype=np.uint8)
    letterbox_gray[letterbox_fan] = rng.integers(15, 65, size=int(letterbox_fan.sum()), dtype=np.uint8)
    letterbox_image = cv2.cvtColor(letterbox_gray, cv2.COLOR_GRAY2BGR)
    cv2.circle(letterbox_image, (320, 240), 55, (10, 10, 10), -1)
    cv2.circle(letterbox_image, (320, 240), 58, (180, 180, 180), 2)
    if not cv2.imwrite(str(letterbox_path), letterbox_image):
        raise OSError("Could not write synthetic non-square letterbox fixture.")
    color_doppler_image = letterbox_image.copy()
    color_doppler_image[100:180, 40:160] = (20, 30, 230)
    if not cv2.imwrite(str(color_doppler_path), color_doppler_image):
        raise OSError("Could not write synthetic color Doppler fixture.")
    print(f"Generated: {left_path} and {right_path}")
    print(f"Generated: {left_jpg_path}")
    print(f"Generated: {letterbox_path}")
    print(f"Generated: {color_doppler_path}")

    # 2. Synthetic DICOM (.dcm)
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid(
        entropy_srcs=[f"synthetic-ultrasound-{seed}-sop-instance"]
    )
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    dcm_path = output_dir / "synthetic_ovary.dcm"
    ds = FileDataset(str(dcm_path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.PatientID = "000000001"
    ds.PatientName = "SYNTHETIC^TEST"
    ds.PatientAge = "034Y"
    ds.StudyDate = "20261025"
    ds.StudyTime = "143000"
    ds.Modality = "US"
    ds.BurnedInAnnotation = "NO"
    ds.NumberOfFrames = 1
    ds.Laterality = "L"
    ds.Manufacturer = "SYNTHETIC FIXTURE"
    ds.ManufacturerModelName = "Synthetic E2E Generator"
    ds.PixelSpacing = [0.1, 0.1]
    ds.Rows = 512
    ds.Columns = 512
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = gray_l.tobytes()
    ds.save_as(str(dcm_path))
    print(f"Generated DICOM: {dcm_path}")

    # 3. Fake corrupted file (text disguised as .png)
    corrupted_path = output_dir / "fake_corrupted.png"
    corrupted_path.write_text("This is an invalid corrupt file with PNG extension for negative testing.", encoding="utf-8")
    print(f"Generated: {corrupted_path}")

    # 4. Zero-byte file
    zero_path = output_dir / "empty_zero_byte.png"
    zero_path.write_bytes(b"")
    print(f"Generated: {zero_path}")

    # 5. Oversized file (> 25MB)
    oversized_path = output_dir / "oversized_26mb.png"
    # Write 26MB of zeros with PNG header
    with open(oversized_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(b"\0" * (26 * 1024 * 1024))
    print(f"Generated: {oversized_path} ({os.path.getsize(oversized_path)} bytes)")
    return output_dir


if __name__ == "__main__":
    generate_fixtures()
