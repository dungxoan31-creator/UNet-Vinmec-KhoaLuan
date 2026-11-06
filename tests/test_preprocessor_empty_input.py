import numpy as np
import pytest


@pytest.mark.parametrize("image", [
    None,
    [],
    np.empty((0, 0), dtype=np.uint8),
    np.zeros(10, dtype=np.uint8),
    np.zeros((20, 20, 2), dtype=np.uint8),
])
def test_preprocess_rejects_empty_input_with_clear_value_error(image):
    from backend.services.preprocessor import UltrasoundPreprocessor

    with pytest.raises(ValueError, match="non-empty image array"):
        UltrasoundPreprocessor().preprocess_for_inference(image)


@pytest.mark.parametrize("image", [None, [], np.empty((0, 0), dtype=np.uint8), np.zeros(10, dtype=np.uint8)])
def test_quality_assessment_returns_consistent_failure_for_invalid_input(image):
    from backend.services.preprocessor import UltrasoundPreprocessor

    report = UltrasoundPreprocessor().assess_image_quality(image)

    assert report["is_acceptable"] is False
    assert report["iqa_score"] == 0.0
    assert report["flags"]
    assert report["message"]


def test_letterbox_resize_preserves_supported_four_channel_input():
    from backend.services.preprocessor import UltrasoundPreprocessor

    image = np.zeros((160, 240, 4), dtype=np.uint8)

    padded, transform = UltrasoundPreprocessor().letterbox_resize(image)

    assert padded.shape == (512, 512, 4)
    assert padded[transform["pad_y"], transform["pad_x"]].shape == (4,)


def test_letterbox_rejects_aspect_ratio_that_collapses_a_resize_dimension():
    from backend.services.preprocessor import UltrasoundPreprocessor

    image = np.zeros((10_000, 1), dtype=np.uint8)

    with pytest.raises(ValueError, match="(?i)collapses a resize dimension"):
        UltrasoundPreprocessor().letterbox_resize(image)


def test_preprocessing_does_not_build_unused_roi_mask(monkeypatch):
    from backend.services.preprocessor import UltrasoundPreprocessor

    preprocessor = UltrasoundPreprocessor()
    monkeypatch.setattr(
        preprocessor,
        "compute_roi_mask",
        lambda *_args, **_kwargs: pytest.fail("Unused ROI masks must not be computed."),
        raising=False,
    )

    _, _, transform, _ = preprocessor.preprocess_for_inference(
        np.full((128, 128), 100, dtype=np.uint8)
    )

    assert "roi_mask" not in transform
