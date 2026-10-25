"""
Generates 100% synthetic ultrasound fixtures for Playwright E2E testing.
Zero patient data. Guaranteed HIPAA/GDPR compliance.
Creates:
1. synthetic_left.png (512x512 synthetic ultrasound)
2. synthetic_right.png (512x512 synthetic ultrasound)
3. synthetic_bilateral.dcm (valid DICOM with PixelSpacing)
4. fake_corrupted.png (invalid text pretending to be png)
5. empty_zero_byte.png (0-byte file)
6. oversized_26mb.png (> 25MB file to test 413 limit)
"""

import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "artifacts" / "synthetic_fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def generate_fixtures():
    # 1. Synthetic 512x512 Ultrasound image (Fan-beam gradient + hypoechoic cyst + hyperechoic wall)
    img_l = np.zeros((512, 512, 3), dtype=np.uint8)
    img_r = np.zeros((512, 512, 3), dtype=np.uint8)

    for y in range(512):
        for x in range(512):
            dist = np.hypot(x - 256, y - 50)
            if 100 < dist < 450:
                speckle = np.random.randint(15, 65)
                img_l[y, x] = [speckle, speckle, speckle]
                img_r[y, x] = [speckle, speckle, speckle]

    # Ovary 1 (Left): cyst centered at (220, 260) with radius 45
    cv2.circle(img_l, (220, 260), 45, (10, 10, 10), -1)
    cv2.circle(img_l, (220, 260), 48, (180, 180, 180), 2)  # Wall

    # Ovary 2 (Right): cyst centered at (280, 270) with radius 55
    cv2.circle(img_r, (280, 270), 55, (12, 12, 12), -1)
    cv2.circle(img_r, (280, 270), 58, (170, 170, 170), 2)

    left_path = FIXTURES_DIR / "synthetic_left.png"
    right_path = FIXTURES_DIR / "synthetic_right.png"
    cv2.imwrite(str(left_path), img_l)
    cv2.imwrite(str(right_path), img_r)
    print(f"Generated: {left_path} and {right_path}")

    # 2. Synthetic DICOM (.dcm)
    try:
        from pydicom.dataset import Dataset, FileDataset
        from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

        dcm_path = FIXTURES_DIR / "synthetic_ovary.dcm"
        ds = FileDataset(str(dcm_path), {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.PatientID = "SYNTH-PID-1029"
        ds.PatientName = "TEST^SYNTHETIC"
        ds.PatientAge = "34Y"
        ds.StudyDate = "20261025"
        ds.StudyTime = "143000"
        ds.Laterality = "L"
        ds.Manufacturer = "Vinmec Ultrasound"
        ds.ManufacturerModelName = "Voluson E10 Synthetic"
        ds.PixelSpacing = [0.1, 0.1]
        ds.Rows = 512
        ds.Columns = 512
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
        ds.PixelData = gray_l.tobytes()
        ds.save_as(str(dcm_path))
        print(f"Generated DICOM: {dcm_path}")
    except Exception as exc:
        print(f"DICOM generation skipped: {exc}")

    # 3. Fake corrupted file (text disguised as .png)
    corrupted_path = FIXTURES_DIR / "fake_corrupted.png"
    corrupted_path.write_text("This is an invalid corrupt file with PNG extension for negative testing.", encoding="utf-8")
    print(f"Generated: {corrupted_path}")

    # 4. Zero-byte file
    zero_path = FIXTURES_DIR / "empty_zero_byte.png"
    zero_path.write_bytes(b"")
    print(f"Generated: {zero_path}")

    # 5. Oversized file (> 25MB)
    oversized_path = FIXTURES_DIR / "oversized_26mb.png"
    # Write 26MB of zeros with PNG header
    with open(oversized_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(b"\0" * (26 * 1024 * 1024))
    print(f"Generated: {oversized_path} ({os.path.getsize(oversized_path)} bytes)")


if __name__ == "__main__":
    generate_fixtures()
