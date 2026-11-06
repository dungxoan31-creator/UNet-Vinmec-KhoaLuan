"""Unit and Empirical Verification Test Suite for Ultrasound Preprocessing Enhancement.

Validates:
- Speckle noise suppression (Lee Filter & SRAD)
- Edge Preservation Index (EPI >= 0.90)
- Signal-to-Noise Ratio (SNR) gain
- Caliper / measurement marker detection specificity and inpainting
- Non-destruction of true ovarian cyst walls
- Pipeline contract alignment with 512x512 Letterbox and CLAHE
"""

from pathlib import Path
import cv2
import numpy as np
import pytest
import torch

from scripts.ultrasound_preprocessing_enhancement import (
    CaliperInpainter,
    SpeckleFilter,
    UltrasoundEnhancer,
    UltrasoundMetrics,
)
from backend.services.preprocessor import UltrasoundPreprocessor


@pytest.fixture
def synthetic_cyst_with_calipers():
    """Generates a synthetic ultrasound image with tissue speckle, anechoic cyst,
    and sonographer caliper crosses with measurement annotations."""
    rng = np.random.RandomState(42)
    # Background parenchyma with Rayleigh-like multiplicative speckle
    base = rng.normal(55, 12, (300, 400)).clip(10, 240).astype(np.uint8)

    # Anechoic unilocular ovarian cyst (center at 200, 150)
    cv2.circle(base, (200, 150), 70, 190, thickness=2)  # Thin cyst wall (stroke ~2px)
    cv2.circle(base, (200, 150), 68, 20, thickness=-1)  # Internal fluid cavity

    # Doctor calipers at vertical diameter (+ markers)
    cv2.drawMarker(base, (200, 80), 255, markerType=cv2.MARKER_CROSS, markerSize=12, thickness=1)
    cv2.drawMarker(base, (200, 220), 255, markerType=cv2.MARKER_CROSS, markerSize=12, thickness=1)

    # Dotted line
    for y in range(86, 215, 6):
        cv2.circle(base, (200, y), 1, 255, -1)

    # Text label
    cv2.putText(base, "D1: 28.0mm", (210, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 255, 1)

    return base


def test_lee_filter_reduces_speckle_and_preserves_edges():
    """Verify Lee filter smooths homogeneous noise while maintaining sharp EPI."""
    clean = np.full((120, 120), 50, dtype=np.float32)
    clean[30:90, 30:90] = 200.0  # Sharp rectangular wall
    rng = np.random.RandomState(123)
    speckle = rng.rayleigh(scale=0.15, size=clean.shape) + 0.85
    noisy = (clean * speckle).clip(0, 255).astype(np.uint8)

    lee_out = SpeckleFilter.lee_filter(noisy, window_size=5, noise_variance=0.04)

    assert lee_out.shape == noisy.shape
    assert lee_out.dtype == np.uint8

    # Edge preservation check
    epi = UltrasoundMetrics.compute_edge_preservation_index(noisy, lee_out)
    assert epi >= 0.92, f"Expected EPI >= 0.92, got {epi}"

    # Homogeneous region SNR check
    snr_metrics = UltrasoundMetrics.compute_snr_gain(noisy[35:85, 35:85], lee_out[35:85, 35:85])
    assert snr_metrics["snr_gain_db"] > 5.0, f"Expected SNR gain > 5.0 dB, got {snr_metrics['snr_gain_db']}"
    assert snr_metrics["variance_reduction_ratio"] > 0.5


def test_srad_filter_convergence_and_edge_preservation():
    """Verify SRAD PDE converges stably without NaN/Inf and preserves boundaries."""
    clean = np.full((100, 100), 40, dtype=np.float32)
    clean[25:75, 25:75] = 190.0
    rng = np.random.RandomState(456)
    speckle = rng.rayleigh(scale=0.12, size=clean.shape) + 0.88
    noisy = (clean * speckle).clip(0, 255).astype(np.uint8)

    srad_out = SpeckleFilter.srad_filter(noisy, n_iter=6, dt=0.1, q0=0.15)

    assert srad_out.shape == noisy.shape
    assert not np.isnan(srad_out).any()
    assert not np.isinf(srad_out).any()

    epi = UltrasoundMetrics.compute_edge_preservation_index(noisy, srad_out)
    assert epi >= 0.95, f"Expected SRAD EPI >= 0.95, got {epi}"

    # Stability across iterations
    srad_12 = SpeckleFilter.srad_filter(noisy, n_iter=12, dt=0.1, q0=0.15)
    assert srad_12.min() >= 0 and srad_12.max() <= 255


def test_caliper_detector_identifies_crosshairs_and_text(synthetic_cyst_with_calipers):
    """Verify caliper detector flags measurement markers, crosses, and text."""
    image = synthetic_cyst_with_calipers
    caliper_mask = CaliperInpainter.detect_calipers(image)

    assert caliper_mask.shape == image.shape
    assert caliper_mask.dtype == np.uint8

    # Ensure crosshairs at (200, 80) and (200, 220) are detected
    assert caliper_mask[80, 200] == 255, "Upper caliper marker not detected"
    assert caliper_mask[220, 200] == 255, "Lower caliper marker not detected"

    # Ensure text annotation area has detected pixels
    text_detected = np.sum(caliper_mask[140:160, 210:280] > 0)
    assert text_detected > 20, "Text annotation pixels not detected"


def test_caliper_detector_preserves_true_cyst_walls():
    """Clinical Safety: Ensure isolated true cyst wall is NOT classified as a caliper."""
    clean_cyst = np.zeros((300, 300), dtype=np.uint8)
    # Complete circular cyst wall (radius 80, thickness 2px, length > 500 px)
    cv2.circle(clean_cyst, (150, 150), 80, 200, thickness=2)

    caliper_mask = CaliperInpainter.detect_calipers(clean_cyst)

    # Large connected cyst wall area (~1000 px) exceeds max_component_area (650)
    # and should be completely preserved (0 false positive pixels)
    wall_false_positives = np.sum(caliper_mask > 0)
    assert wall_false_positives == 0, f"False positive detection on true cyst wall: {wall_false_positives} px"


def test_caliper_inpainting_restores_texture(synthetic_cyst_with_calipers):
    """Verify inpainting replaces artificial caliper/text values smoothly."""
    image = synthetic_cyst_with_calipers
    inpainter = CaliperInpainter(inpaint_method="telea", inpaint_radius=3)

    inpainted, mask = inpainter.inpaint(image)

    assert np.sum(mask > 0) > 0
    # Before inpainting, detected marker pixels are bright (>= 238) with average > 250
    assert np.all(image[mask > 0] >= 238)
    assert np.mean(image[mask > 0]) > 250.0

    # After inpainting, caliper pixels are smoothly restored to surrounding ultrasound levels (< 200)
    assert np.mean(inpainted[mask > 0]) < 180.0


def test_enhancer_full_pipeline_contract(synthetic_cyst_with_calipers):
    """Verify UltrasoundEnhancer returns expected PyTorch tensor, dimensions, and metadata."""
    enhancer = UltrasoundEnhancer(
        target_size=(512, 512),
        denoise_method="lee",
        enable_caliper_removal=True,
    )

    result = enhancer.enhance_and_preprocess(synthetic_cyst_with_calipers)

    # 1. Output tensor checks
    tensor = result["tensor"]
    assert isinstance(tensor, torch.Tensor)
    assert tensor.shape == (1, 1, 512, 512)
    assert tensor.dtype == torch.float32
    assert 0.0 <= float(tensor.min()) and float(tensor.max()) <= 1.0

    # 2. Intermediate shapes
    assert result["enhanced_512"].shape == (512, 512)
    assert result["padded_512"].shape == (512, 512)
    assert result["inpainted_gray"].shape == synthetic_cyst_with_calipers.shape
    assert result["denoised_gray"].shape == synthetic_cyst_with_calipers.shape
    assert result["caliper_mask"].shape == synthetic_cyst_with_calipers.shape

    # 3. Transform params
    params = result["transform_params"]
    assert params["target_w"] == 512 and params["target_h"] == 512
    assert params["orig_w"] == synthetic_cyst_with_calipers.shape[1]
    assert params["orig_h"] == synthetic_cyst_with_calipers.shape[0]

    # 4. Interoperability with UltrasoundPreprocessor inverse_letterbox_mask
    mask_512 = np.zeros((512, 512), dtype=np.uint8)
    mask_512[200:300, 200:300] = 255
    restored_mask = UltrasoundPreprocessor().inverse_letterbox_mask(mask_512, params)
    assert restored_mask.shape == synthetic_cyst_with_calipers.shape


def test_real_clinical_image_processing_lee_and_srad():
    """Verify processing on real clinical image dataset/2d/images/1.JPG passes 100%."""
    sample_path = Path("dataset/2d/images/1.JPG")
    if not sample_path.exists():
        pytest.skip("dataset/2d/images/1.JPG not present in workspace")

    img = cv2.imread(str(sample_path))
    assert img is not None

    enhancer_lee = UltrasoundEnhancer(denoise_method="lee")
    res_lee = enhancer_lee.enhance_and_preprocess(img)

    assert res_lee["tensor"].shape == (1, 1, 512, 512)
    assert res_lee["metrics"]["edge_preservation_index"] > 0.85

    enhancer_srad = UltrasoundEnhancer(denoise_method="srad", srad_iterations=4)
    res_srad = enhancer_srad.enhance_and_preprocess(img)

    assert res_srad["tensor"].shape == (1, 1, 512, 512)
    assert res_srad["metrics"]["edge_preservation_index"] > 0.90


def test_invalid_input_raises_value_error():
    """Verify empty or invalid inputs raise clear ValueError."""
    enhancer = UltrasoundEnhancer()

    with pytest.raises(ValueError, match="non-empty NumPy array"):
        enhancer.enhance_and_preprocess(np.empty((0, 0)))

    with pytest.raises(ValueError, match="non-empty NumPy array"):
        enhancer.enhance_and_preprocess(None)
