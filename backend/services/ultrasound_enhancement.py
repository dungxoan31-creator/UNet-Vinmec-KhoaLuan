"""Ultrasound Preprocessing Enhancement Module:
Advanced Speckle Reduction (SRAD & Lee Filter),
Acoustic Caliper / Marker Detection & Inpainting (Telea / Navier-Stokes),
and Pipeline Normalization (Letterbox 512x512 + CLAHE).

Designed for Transvaginal/Pelvic Ovarian Ultrasound Analysis with
Clinical Edge Preservation for thin cyst walls (<2-3 mm) and septations.
"""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np
import torch

logger = logging.getLogger("ultrasound_preprocessing_enhancement")


# ==============================================================================
# 1. SPECKLE NOISE REDUCTION FILTERS (SRAD & LEE)
# ==============================================================================

class SpeckleFilter:
    """Acoustic speckle reduction filters preserving thin ovarian cyst boundaries.

    Speckle noise in B-mode ultrasound is multiplicative (Rayleigh/Rice distribution).
    Standard linear Gaussian/Mean filtering blurs delicate interfaces (<2-3 mm).
    Adaptive and anisotropic diffusion filters selectively smooth homogeneous anechoic
    fluid and parenchyma while freezing diffusion at strong wall gradients.
    """

    @staticmethod
    def lee_filter(
        image_gray: np.ndarray,
        window_size: int = 5,
        noise_variance: float = 0.04,
    ) -> np.ndarray:
        """Adaptive Lee Filter for multiplicative ultrasound speckle noise.

        Model: intensity(x, y) = R(x, y) * eta(x, y), where eta ~ (1, sigma_eta^2).
        Weight: W = max(0, (var_I - sigma_eta^2 * mean_I^2) / var_I)
        Estimate: R_hat = mean_I + W * (intensity - mean_I)

        Args:
            image_gray: 2D uint8 or float32 grayscale image.
            window_size: Local neighborhood window size (must be odd, e.g., 3, 5, 7).
            noise_variance: Estimated speckle noise variance (typically 0.02 - 0.08).

        Returns:
            Denoised 2D uint8 image with preserved edges.
        """
        if window_size % 2 == 0:
            window_size += 1

        img_float = image_gray.astype(np.float32)
        ksize = (window_size, window_size)

        # Fast local mean and variance using box filter O(1) per pixel
        local_mean = cv2.boxFilter(img_float, -1, ksize, borderType=cv2.BORDER_REFLECT)
        local_sq_mean = cv2.boxFilter(img_float ** 2, -1, ksize, borderType=cv2.BORDER_REFLECT)
        local_var = np.maximum(0.0, local_sq_mean - local_mean ** 2)

        # Multiplicative noise formula
        noise_term = noise_variance * (local_mean ** 2)
        denom = local_var + 1e-6
        weight = np.maximum(0.0, (local_var - noise_term) / denom)
        weight = np.clip(weight, 0.0, 1.0)

        filtered = local_mean + weight * (img_float - local_mean)
        return np.clip(filtered, 0.0, 255.0).astype(np.uint8)

    @staticmethod
    def srad_filter(
        image_gray: np.ndarray,
        n_iter: int = 8,
        dt: float = 0.1,
        q0: float = 0.15,
        rho: float = 0.05,
        num_iter: int | None = None,
    ) -> np.ndarray:
        if num_iter is not None:
            n_iter = num_iter
        """Speckle Reducing Anisotropic Diffusion (SRAD) filter.

        Reference:
            Yu, Y. and Acton, S.T., "Speckle Reducing Anisotropic Diffusion",
            IEEE Transactions on Image Processing, 11(11):1260-1270, 2002.

        PDE formulation:
            dI/dt = div[c(q) * grad(intensity)]
            where q is the instantaneous coefficient of variation and c(q)
            is the diffusion coefficient.

        Args:
            image_gray: 2D uint8 or float32 grayscale image.
            n_iter: Number of diffusion iterations (default 8).
            dt: Time step size (must be <= 0.25 for stability).
            q0: Initial speckle scale parameter.
            rho: Exponential decay rate for q0(t).

        Returns:
            Denoised 2D uint8 image with sharp boundaries.
        """
        intensity = image_gray.astype(np.float32) / 255.0
        dt = min(max(dt, 0.01), 0.25)

        for t in range(n_iter):
            # Directional forward differences (Right, Left, Down, Up)
            dR = np.pad(intensity[1:, :] - intensity[:-1, :], ((0, 1), (0, 0)), mode="edge")
            dL = np.pad(intensity[1:, :] - intensity[:-1, :], ((1, 0), (0, 0)), mode="edge")
            dD = np.pad(intensity[:, 1:] - intensity[:, :-1], ((0, 0), (0, 1)), mode="edge")
            dU = np.pad(intensity[:, 1:] - intensity[:, :-1], ((0, 0), (1, 0)), mode="edge")

            safe_intensity = np.maximum(intensity, 1e-4)

            # Gradient magnitude squared and Laplacian approximation
            grad_sq = (dR**2 + dL**2 + dD**2 + dU**2) / (safe_intensity**2 + 1e-8)
            lap = (dR - dL + dD - dU) / (safe_intensity + 1e-8)

            # Instantaneous coefficient of variation q
            num = 0.5 * grad_sq - (1.0 / 16.0) * (lap**2)
            den = (1.0 + 0.25 * lap)**2
            q_sq = np.maximum(0.0, num / (den + 1e-8))

            # Adaptive speckle scale parameter q0(t)
            q0_t_sq = (q0 * np.exp(-rho * t))**2
            c = 1.0 / (1.0 + (q_sq - q0_t_sq) / (q0_t_sq * (1.0 + q0_t_sq) + 1e-8))
            c = np.clip(c, 0.0, 1.0)

            # Conservative divergence discretization
            cR = np.pad(c[1:, :] + c[:-1, :], ((0, 1), (0, 0)), mode="edge") * 0.5
            cL = np.pad(c[1:, :] + c[:-1, :], ((1, 0), (0, 0)), mode="edge") * 0.5
            cD = np.pad(c[:, 1:] + c[:, :-1], ((0, 0), (0, 1)), mode="edge") * 0.5
            cU = np.pad(c[:, 1:] + c[:, :-1], ((0, 0), (1, 0)), mode="edge") * 0.5

            div = cR * dR - cL * dL + cD * dD - cU * dU
            intensity = intensity + (dt / 4.0) * div
            intensity = np.clip(intensity, 0.0, 1.0)

        return (intensity * 255.0).astype(np.uint8)


# ==============================================================================
# 2. CALIPER & MEASUREMENT MARKER INPAINTING
# ==============================================================================

class CaliperInpainter:
    """Detects and inpaints clinical calipers, measurement crosses, tick lines,
    dotted lines, and text annotations on ultrasound frames.

    Protects true biological structures (cyst walls, papillae, septations)
    by analyzing geometric compactness, stroke thickness, and intensity profiles.
    """

    def __init__(self, inpaint_method: str = "telea", inpaint_radius: int = 3):
        """Initialize CaliperInpainter.

        Args:
            inpaint_method: 'telea' (Alexandru Telea Fast Marching) or 'ns' (Navier-Stokes).
            inpaint_radius: Inpainting neighborhood radius (default 3 px).
        """
        self.method_flag = cv2.INPAINT_TELEA if inpaint_method.lower() == "telea" else cv2.INPAINT_NS
        self.inpaint_radius = inpaint_radius

    @staticmethod
    def detect_calipers(
        image_np: np.ndarray,
        intensity_threshold: int = 238,
        max_stroke_thickness: float = 2.4,
        max_component_area: int = 650,
        min_component_area: int = 2,
    ) -> np.ndarray:
        """Detect synthetic ultrasound calipers, crosshairs, tick marks, and text overlays.

        Args:
            image_np: 2D grayscale or 3D BGR image.
            intensity_threshold: Intensity cutoff for bright synthetic markers.
            max_stroke_thickness: Maximum half-stroke thickness (via distance transform).
            max_component_area: Maximum pixel area for single marker components.
            min_component_area: Minimum pixel area to reject single isolated noisy pixels.

        Returns:
            Binary mask (2D uint8) of detected calipers (255 for marker, 0 elsewhere).
        """
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
            # Detect colored calipers (yellow, cyan, green calipers in Doppler or modern machines)
            b, g, r = image_np[:, :, 0], image_np[:, :, 1], image_np[:, :, 2]
            color_diff = np.maximum(
                np.abs(r.astype(np.int16) - g.astype(np.int16)),
                np.maximum(
                    np.abs(r.astype(np.int16) - b.astype(np.int16)),
                    np.abs(g.astype(np.int16) - b.astype(np.int16)),
                ),
            )
            color_marker_candidates = (color_diff > 30) & (gray > 80)
        else:
            gray = image_np.copy()
            color_marker_candidates = np.zeros_like(gray, dtype=bool)

        # High-intensity thresholding for bright annotations & calipers
        _, bright_mask = cv2.threshold(gray, intensity_threshold, 255, cv2.THRESH_BINARY)
        candidate_mask = cv2.bitwise_or(bright_mask, (color_marker_candidates.astype(np.uint8) * 255))

        # Geometric crosshair opening kernels (detects '+' and 'x' shapes)
        k_cross5 = cv2.getStructuringElement(cv2.MORPH_CROSS, (5, 5))
        cross_hits = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, k_cross5)

        k_diag5 = np.zeros((5, 5), dtype=np.uint8)
        np.fill_diagonal(k_diag5, 1)
        np.fill_diagonal(np.fliplr(k_diag5), 1)
        diag_hits = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, k_diag5)
        has_cross_feature = (cross_hits > 0) | (diag_hits > 0)

        # Connected component structural filtering
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(candidate_mask)
        marker_mask = np.zeros_like(gray, dtype=np.uint8)

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]

            # True biological cyst walls typically span larger connected areas (> 800-2000 px).
            # Calipers, ticks, dotted lines, and characters are compact/small.
            if min_component_area <= area <= max_component_area and w <= 160 and h <= 80:
                comp_binary = (labels == i).astype(np.uint8) * 255
                # Distance transform to verify thin synthetic stroke (<= max_stroke_thickness)
                dist = cv2.distanceTransform(comp_binary, cv2.DIST_L2, 3)
                max_dist = dist.max()

                elongation = max(w, h) / max(min(w, h), 1)
                comp_has_cross = np.any(has_cross_feature[labels == i])

                # Anatomical structure preservation (F03 fix):
                # Thin septations and cyst wall boundaries are continuous linear strokes.
                # If an elongated bright stroke (length >= 15px, elongation >= 3.0) lacks
                # any crosshair or diagonal junction, it is anatomical and must NEVER be inpainted.
                if max(w, h) >= 15 and elongation >= 3.0 and not comp_has_cross:
                    continue

                # Stroke thickness constraint: ultrasound calipers and text have stroke <= 2-3px
                if comp_has_cross and max_dist <= max_stroke_thickness + 1.0:
                    marker_mask = cv2.bitwise_or(marker_mask, comp_binary)
                elif not comp_has_cross and max_dist <= max_stroke_thickness and max(w, h) < 15:
                    # Small alphanumeric characters / dots
                    marker_mask = cv2.bitwise_or(marker_mask, comp_binary)

        return marker_mask

    def inpaint(
        self,
        image_np: np.ndarray,
        marker_mask: np.ndarray | None = None,
        dilate_radius: int = 1,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Inpaint detected caliper regions using Telea or Navier-Stokes algorithms.

        Args:
            image_np: Input 2D grayscale or 3D BGR image.
            marker_mask: Optional precomputed caliper mask. If None, auto-detected.
            dilate_radius: Mask dilation radius to cover anti-aliasing edge halos.

        Returns:
            Tuple of (inpainted_image, detected_marker_mask).
        """
        if marker_mask is None:
            marker_mask = self.detect_calipers(image_np)

        if np.sum(marker_mask) == 0:
            return image_np.copy(), marker_mask

        # Dilate slightly to ensure full coverage of boundary pixels
        if dilate_radius > 0:
            ksize = 2 * dilate_radius + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
            inp_mask = cv2.dilate(marker_mask, kernel)
        else:
            inp_mask = marker_mask

        # Apply OpenCV inpainting
        inpainted = cv2.inpaint(image_np, inp_mask, inpaintRadius=self.inpaint_radius, flags=self.method_flag)
        return inpainted, marker_mask


# ==============================================================================
# 3. QUANTITATIVE CLINICAL & IMAGE QUALITY METRICS
# ==============================================================================

class UltrasoundMetrics:
    """Quantitative performance metrics for speckle reduction & edge preservation."""

    @staticmethod
    def compute_edge_preservation_index(
        original: np.ndarray,
        filtered: np.ndarray,
        percentile_thresh: float = 75.0,
    ) -> float:
        """Compute the Edge Preservation Index (EPI / Pratt correlation coefficient).

        Evaluates the correlation of high-pass gradient vectors between the original
        and filtered images along high-gradient edge contours (cyst walls).
        EPI in [0.85, 1.0] indicates exceptional boundary retention without blurring.
        """
        orig_f = original.astype(np.float32)
        filt_f = filtered.astype(np.float32)

        # Sobel gradients
        gx_orig = cv2.Sobel(orig_f, cv2.CV_32F, 1, 0, ksize=3)
        gy_orig = cv2.Sobel(orig_f, cv2.CV_32F, 0, 1, ksize=3)
        grad_orig = np.hypot(gx_orig, gy_orig)

        gx_filt = cv2.Sobel(filt_f, cv2.CV_32F, 1, 0, ksize=3)
        gy_filt = cv2.Sobel(filt_f, cv2.CV_32F, 0, 1, ksize=3)
        grad_filt = np.hypot(gx_filt, gy_filt)

        # Identify salient boundary edges
        edge_mask = grad_orig > np.percentile(grad_orig, percentile_thresh)
        if np.sum(edge_mask) < 20:
            return 1.0

        g1 = grad_orig[edge_mask]
        g2 = grad_filt[edge_mask]

        g1_dev = g1 - np.mean(g1)
        g2_dev = g2 - np.mean(g2)

        numerator = np.sum(g1_dev * g2_dev)
        denominator = np.sqrt(np.sum(g1_dev**2) * np.sum(g2_dev**2)) + 1e-8
        epi = float(numerator / denominator)
        return round(float(np.clip(epi, -1.0, 1.0)), 4)

    @staticmethod
    def compute_snr_gain(
        noisy_roi: np.ndarray,
        filtered_roi: np.ndarray,
    ) -> dict[str, float]:
        """Compute Signal-to-Noise Ratio (SNR) and gain in dB for a homogeneous region."""
        n_float = noisy_roi.astype(np.float32)
        f_float = filtered_roi.astype(np.float32)

        mean_n, std_n = float(np.mean(n_float)), float(np.std(n_float))
        mean_f, std_f = float(np.mean(f_float)), float(np.std(f_float))

        snr_pre = 10.0 * np.log10((mean_n**2) / (std_n**2 + 1e-8) + 1e-8)
        snr_post = 10.0 * np.log10((mean_f**2) / (std_f**2 + 1e-8) + 1e-8)
        snr_gain = snr_post - snr_pre

        return {
            "snr_pre_db": round(snr_pre, 2),
            "snr_post_db": round(snr_post, 2),
            "snr_gain_db": round(snr_gain, 2),
            "variance_reduction_ratio": round(float((std_n**2 - std_f**2) / (std_n**2 + 1e-8)), 4),
        }

    @staticmethod
    def compute_equivalent_number_of_looks(roi: np.ndarray) -> float:
        """Compute Equivalent Number of Looks (ENL = mean^2 / var) in homogeneous tissue."""
        r_float = roi.astype(np.float32)
        mean_val = float(np.mean(r_float))
        var_val = float(np.var(r_float))
        if var_val < 1e-6:
            return 100.0
        return round(float((mean_val**2) / var_val), 2)

    @staticmethod
    def compute_cnr(
        image: np.ndarray,
        lesion_mask: np.ndarray,
        background_mask: np.ndarray,
    ) -> float:
        """Compute Contrast-to-Noise Ratio (CNR) between lesion interior and surrounding tissue."""
        img_f = image.astype(np.float32)
        lesion_vals = img_f[lesion_mask > 0]
        bg_vals = img_f[background_mask > 0]

        if lesion_vals.size == 0 or bg_vals.size == 0:
            return 0.0

        mu_l, var_l = float(np.mean(lesion_vals)), float(np.var(lesion_vals))
        mu_b, var_b = float(np.mean(bg_vals)), float(np.var(bg_vals))

        cnr = np.abs(mu_l - mu_b) / np.sqrt(var_l + var_b + 1e-8)
        return round(float(cnr), 3)

    @staticmethod
    def compute_psnr_and_ssim(
        reference: np.ndarray,
        target: np.ndarray,
    ) -> dict[str, float]:
        """Compute Peak Signal-to-Noise Ratio (PSNR) and approximate SSIM."""
        ref_f = reference.astype(np.float32)
        tar_f = target.astype(np.float32)

        mse = float(np.mean((ref_f - tar_f) ** 2))
        if mse < 1e-8:
            psnr = 100.0
        else:
            psnr = float(10.0 * np.log10((255.0**2) / mse))

        # Structural Similarity (SSIM simplified window)
        c1 = (0.01 * 255.0) ** 2
        c2 = (0.03 * 255.0) ** 2

        mu_x = float(np.mean(ref_f))
        mu_y = float(np.mean(tar_f))
        var_x = float(np.var(ref_f))
        var_y = float(np.var(tar_f))
        cov_xy = float(np.mean((ref_f - mu_x) * (tar_f - mu_y)))

        ssim_num = (2.0 * mu_x * mu_y + c1) * (2.0 * cov_xy + c2)
        ssim_den = (mu_x**2 + mu_y**2 + c1) * (var_x + var_y + c2)
        ssim = float(ssim_num / (ssim_den + 1e-8))

        return {
            "psnr_db": round(psnr, 2),
            "ssim": round(float(np.clip(ssim, -1.0, 1.0)), 4),
        }


# ==============================================================================
# 4. UNIFIED ENHANCEMENT & PREPROCESSING PIPELINE
# ==============================================================================

class UltrasoundEnhancer:
    """Integrated Preprocessing & Enhancement Engine for Ovarian Ultrasound Analysis.

    Sequence:
        1. Caliper & marker detection + inpainting (Telea or Navier-Stokes)
        2. Edge-preserving speckle noise reduction (SRAD or Lee filter)
        3. Aspect-ratio preserving letterbox resize to target size (512x512)
        4. Contrast-Limited Adaptive Histogram Equalization (CLAHE)
        5. Tensor normalization to PyTorch tensor shape (1, 1, 512, 512)
    """

    def __init__(
        self,
        target_size: tuple[int, int] = (512, 512),
        clahe_clip_limit: float = 2.0,
        clahe_grid_size: tuple[int, int] = (8, 8),
        denoise_method: str = "lee",
        inpaint_method: str = "telea",
        enable_caliper_removal: bool = True,
        srad_iterations: int = 6,
        lee_window_size: int = 5,
        lee_noise_var: float = 0.04,
    ):
        self.target_size = target_size
        self.clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=clahe_grid_size)
        self.denoise_method = denoise_method.lower()
        self.enable_caliper_removal = enable_caliper_removal
        self.inpainter = CaliperInpainter(inpaint_method=inpaint_method)
        self.speckle_filter = SpeckleFilter()
        self.srad_iterations = srad_iterations
        self.lee_window_size = lee_window_size
        self.lee_noise_var = lee_noise_var

    def letterbox_resize(
        self,
        image_np: np.ndarray,
        target_size: tuple[int, int] | None = None,
        is_mask: bool = False,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Letterbox resize preserving exact aspect ratio via symmetric black borders.

        Matches UltrasoundPreprocessor specification for zero-drift inference.
        """
        if target_size is None:
            target_size = self.target_size

        target_w, target_h = target_size
        orig_h, orig_w = image_np.shape[:2]

        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        if new_w < 1 or new_h < 1:
            raise ValueError("Input aspect ratio collapses a resize dimension at target size.")

        interp = cv2.INTER_NEAREST if is_mask else cv2.INTER_LINEAR
        resized = cv2.resize(image_np, (new_w, new_h), interpolation=interp)

        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2

        if len(image_np.shape) == 3:
            padded = np.zeros((target_h, target_w, image_np.shape[2]), dtype=image_np.dtype)
            padded[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
        else:
            padded = np.zeros((target_h, target_w), dtype=image_np.dtype)
            padded[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        transform_params = {
            "scale": scale,
            "pad_x": pad_x,
            "pad_y": pad_y,
            "pad_w": pad_x,
            "pad_h": pad_y,
            "new_w": new_w,
            "new_h": new_h,
            "orig_w": orig_w,
            "orig_h": orig_h,
            "target_w": target_w,
            "target_h": target_h,
        }
        return padded, transform_params

    def enhance_and_preprocess(
        self,
        image_np: np.ndarray,
        denoise_override: str | None = None,
        inpaint_override: bool | None = None,
    ) -> dict[str, Any]:
        """Execute full end-to-end preprocessing & enhancement pipeline.

        Args:
            image_np: Raw input image (2D grayscale, 3-channel BGR, or 4-channel BGRA).
            denoise_override: Optional override for denoise_method ('lee', 'srad', 'none').
            inpaint_override: Optional override for enable_caliper_removal (bool).

        Returns:
            Dictionary containing:
                - tensor: PyTorch torch.Tensor (1, 1, 512, 512), range [0, 1]
                - enhanced_512: 512x512 uint8 image after CLAHE
                - padded_512: 512x512 uint8 image before CLAHE
                - inpainted_gray: Original size grayscale after caliper removal
                - denoised_gray: Original size grayscale after speckle filtering
                - caliper_mask: Original size binary mask of detected calipers
                - transform_params: Scaling and padding metadata
                - metrics: Quantitative EPI, SNR gain, ENL, and similarity scores
        """
        if not isinstance(image_np, np.ndarray) or image_np.size == 0:
            raise ValueError("Input image_np must be a valid non-empty NumPy array.")

        # 1. Grayscale normalization
        if len(image_np.shape) == 3:
            orig_gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        else:
            orig_gray = image_np.copy()

        do_inpaint = self.enable_caliper_removal if inpaint_override is None else inpaint_override
        denoise_mode = self.denoise_method if denoise_override is None else denoise_override.lower()

        # 2. Inpainting calipers & markers
        caliper_mask = np.zeros_like(orig_gray, dtype=np.uint8)
        if do_inpaint:
            inpainted_gray, caliper_mask = self.inpainter.inpaint(orig_gray)
        else:
            inpainted_gray = orig_gray.copy()

        # 3. Speckle noise filtering
        if denoise_mode == "lee":
            denoised_gray = self.speckle_filter.lee_filter(
                inpainted_gray,
                window_size=self.lee_window_size,
                noise_variance=self.lee_noise_var,
            )
        elif denoise_mode == "srad":
            denoised_gray = self.speckle_filter.srad_filter(
                inpainted_gray,
                n_iter=self.srad_iterations,
                dt=0.1,
                q0=0.15,
            )
        else:
            denoised_gray = inpainted_gray.copy()

        # 4. Aspect-ratio preserving letterbox resize (512x512)
        padded_512, transform_params = self.letterbox_resize(denoised_gray, self.target_size)

        # 5. CLAHE contrast enhancement
        enhanced_512 = self.clahe.apply(padded_512)

        # 6. Tensor normalization
        tensor_float = enhanced_512.astype(np.float32) / 255.0
        torch_tensor = torch.from_numpy(tensor_float).unsqueeze(0).unsqueeze(0)  # (1, 1, H, W)

        # 7. Comprehensive Quantitative Metrics
        epi_score = UltrasoundMetrics.compute_edge_preservation_index(inpainted_gray, denoised_gray)
        enl_orig = UltrasoundMetrics.compute_equivalent_number_of_looks(orig_gray)
        enl_denoised = UltrasoundMetrics.compute_equivalent_number_of_looks(denoised_gray)
        snr_metrics = UltrasoundMetrics.compute_snr_gain(orig_gray, denoised_gray)
        sim_metrics = UltrasoundMetrics.compute_psnr_and_ssim(orig_gray, denoised_gray)

        metrics = {
            "edge_preservation_index": epi_score,
            "enl_original": enl_orig,
            "enl_denoised": enl_denoised,
            "enl_improvement_ratio": round(enl_denoised / (enl_orig + 1e-6), 2),
            "snr_pre_db": snr_metrics["snr_pre_db"],
            "snr_post_db": snr_metrics["snr_post_db"],
            "snr_gain_db": snr_metrics["snr_gain_db"],
            "psnr_db": sim_metrics["psnr_db"],
            "ssim": sim_metrics["ssim"],
            "caliper_pixels_detected": int(np.sum(caliper_mask > 0)),
            "denoise_method": denoise_mode,
            "inpaint_enabled": do_inpaint,
        }

        return {
            "tensor": torch_tensor,
            "enhanced_512": enhanced_512,
            "padded_512": padded_512,
            "inpainted_gray": inpainted_gray,
            "denoised_gray": denoised_gray,
            "caliper_mask": caliper_mask,
            "transform_params": transform_params,
            "metrics": metrics,
        }


# ==============================================================================
# 5. DEMONSTRATION & BENCHMARK RUNNER
# ==============================================================================
