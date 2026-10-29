import cv2
import numpy as np

from backend.services.inference_engine import InferenceEngine
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.report_generator import build_structured_findings_report
from backend.services.source_measurements import measure_source_mask


def test_extract_calipers_and_measurements_includes_watershed_follicles():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 0.1

    mask = np.zeros((512, 512), dtype=np.uint8)
    # Two touching circular follicles: center1=(200, 200), center2=(200, 224), r=14 (overlap by 4px)
    cv2.circle(mask, (200, 200), 14, 1, -1)
    cv2.circle(mask, (200, 224), 14, 1, -1)

    # With pixel_spacing_mm = 0.2:
    # Radius 14px -> Diameter ~28px -> ~5.6mm (which is within PCOS range 2.0 - 9.0 mm)
    res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=0.2)

    assert "follicles" in res
    follicles = res["follicles"]
    assert follicles["count"] == 2
    assert follicles["count_in_range"] == 2
    assert len(follicles["diameters_px"]) == 2
    assert len(follicles["diameters_mm"]) == 2
    for d in follicles["diameters_mm"]:
        assert 5.0 <= d <= 6.2


def test_extract_calipers_empty_mask_follicles():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 0.1

    empty_mask = np.zeros((512, 512), dtype=np.uint8)
    res = engine.extract_calipers_and_measurements(empty_mask, pixel_spacing_mm=0.2)

    assert "follicles" in res
    assert res["follicles"]["count"] == 0
    assert res["follicles"]["count_in_range"] == 0
    assert res["follicles"]["diameters_px"] == []
    assert res["follicles"]["diameters_mm"] is None


def test_measure_source_mask_recalibrates_follicles():
    engine = InferenceEngine(device="cpu", architecture="unetplusplus_resnet34")
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))

    # Synthetic decoded source image: 400x400
    decoded = np.zeros((400, 400), dtype=np.uint8)

    # Create mask on 512x512
    mask_512 = np.zeros((512, 512), dtype=np.uint8)
    # Draw two follicles in the middle (pad area)
    cv2.circle(mask_512, (256, 256), 15, 1, -1)
    cv2.circle(mask_512, (256, 280), 15, 1, -1)
    rle = engine.mask_to_rle(mask_512)

    # 1. Uncalibrated test
    meas_uncal = measure_source_mask(
        decoded=decoded,
        rle_mask=rle,
        preprocessor=preprocessor,
        engine=engine,
        calibration={"pixel_spacing_mm": None, "calibrated": False, "calibration_source": "NONE"},
    )
    assert "follicles" in meas_uncal
    assert meas_uncal["follicles"]["count"] >= 1
    assert meas_uncal["follicles"]["diameters_mm"] is None
    assert meas_uncal["follicles"]["count_in_range"] is None

    # 2. Calibrated test (spacing = 0.25 mm/px)
    meas_cal = measure_source_mask(
        decoded=decoded,
        rle_mask=rle,
        preprocessor=preprocessor,
        engine=engine,
        calibration={"pixel_spacing_mm": 0.25, "calibrated": True, "calibration_source": "MANUAL"},
    )
    assert "follicles" in meas_cal
    assert meas_cal["follicles"]["count"] >= 1
    assert meas_cal["follicles"]["diameters_mm"] is not None
    assert len(meas_cal["follicles"]["diameters_mm"]) == meas_cal["follicles"]["count"]
    # Check that count_in_range corresponds to follicles in 2.0-9.0mm
    expected_in_range = sum(2.0 <= d <= 9.0 for d in meas_cal["follicles"]["diameters_mm"])
    assert meas_cal["follicles"]["count_in_range"] == expected_in_range


def test_report_generator_withholds_mm_range_count_without_pixel_spacing():
    findings = {
        "side": "left",
        "measurements": {
            "follicles": {
                "count": 14,
                "count_in_range": 12,
                "diameters_mm": [3.2, 4.1, 5.0],
            }
        }
    }
    report = build_structured_findings_report(findings)
    assert "- Số vùng ứng viên trên mask (chưa xác nhận là nang): 14 (trong khoảng kích thước cấu hình: không xác định)." in report


def test_report_generator_formats_follicle_range_count_with_valid_pixel_spacing():
    findings = {
        "side": "left",
        "pixel_spacing_mm": 0.1,
        "measurements": {
            "follicles": {
                "count": 14,
                "count_in_range": 12,
                "diameters_mm": [3.2, 4.1, 5.0],
            }
        },
    }

    report = build_structured_findings_report(findings)

    assert "- Số vùng ứng viên trên mask (chưa xác nhận là nang): 14 (trong khoảng kích thước cấu hình: 12)." in report
