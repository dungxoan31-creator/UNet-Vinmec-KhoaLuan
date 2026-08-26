"""
Utility script to generate realistic synthetic ultrasound images & masks
for immediate local testing, verification, and demo.
Generates:
1. normal_ovary.png (Empty Mask - True Negative)
2. simple_cyst.png (Anechoic round cyst with clean thin wall)
3. dermoid_cyst.png (Echogenic solid-cystic lesion with acoustic shadow)
4. endometrioma.png (Ground-glass low-level echo cyst)
"""

import os

import cv2
import numpy as np


def generate_ultrasound_cone(h=512, w=512):
    """
    Generates a fan-beam ultrasound background with speckle noise and acoustic attenuation.
    """
    canvas = np.zeros((h, w), dtype=np.uint8)

    # Fan beam geometry (Apex at top center)
    apex = (w // 2, 40)
    radius = 430
    start_angle = 35
    end_angle = 145

    # Draw active ultrasound sector
    cv2.ellipse(canvas, apex, (radius, radius), 0, start_angle, end_angle, 100, -1)

    # Add Rayleigh/Gaussian speckle noise to simulate ultrasound tissue
    noise = np.random.normal(loc=60, scale=25, size=(h, w)).astype(np.float32)
    # Distance attenuation from apex
    y_coords, x_coords = np.indices((h, w))
    dist_from_apex = np.sqrt((x_coords - apex[0]) ** 2 + (y_coords - apex[1]) ** 2)
    attenuation = np.clip(1.0 - (dist_from_apex / 550.0) * 0.4, 0.4, 1.0)

    tissue = (noise * attenuation).astype(np.uint8)
    tissue_masked = cv2.bitwise_and(tissue, tissue, mask=canvas)

    # Draw realistic ovary oval stroma
    ovary_center = (w // 2, 260)
    ovary_axes = (140, 95)
    ovary_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(ovary_mask, ovary_center, ovary_axes, -10, 0, 360, 255, -1)

    # Ovary stroma is slightly brighter speckle
    ovary_speckle = np.random.normal(loc=85, scale=20, size=(h, w)).astype(np.uint8)
    tissue_masked = np.where(ovary_mask == 255, ovary_speckle, tissue_masked)

    # Add ultrasound calibration ruler and sector outline
    cv2.ellipse(tissue_masked, apex, (radius, radius), 0, start_angle, end_angle, 180, 2)

    return tissue_masked, ovary_center, ovary_axes


def create_sample_dataset(output_dir="data/sample_cases"):
    os.makedirs(output_dir, exist_ok=True)

    samples = [
        ("case_01_normal_ovary", "NORMAL", "Empty Mask (True Negative)"),
        ("case_02_simple_cyst", "CYSTIC", "Simple Serous Cyst (32mm)"),
        ("case_03_dermoid_cyst", "DERMOID", "Dermoid Cyst (Teratoma 41mm)"),
        ("case_04_endometrioma", "ENDOMETRIOMA", "Endometrioma / Chocolate Cyst (28mm)"),
    ]

    for name, lesion_type, desc in samples:
        us_img, ov_cx, _ov_axes = generate_ultrasound_cone()
        mask = np.zeros((512, 512), dtype=np.uint8)

        if lesion_type == "NORMAL":
            # Normal ovary has few tiny normal physiological follicles (<8mm)
            for offset in [(-35, -15, 12), (25, 20, 10), (10, -25, 8)]:
                fc = (ov_cx[0] + offset[0], ov_cx[1] + offset[1])
                cv2.circle(us_img, fc, offset[2], 25, -1)  # Dark anechoic follicle
            # Mask stays completely empty (0s)

        elif lesion_type == "CYSTIC":
            # Round anechoic fluid-filled cyst with posterior acoustic enhancement
            cyst_center = (ov_cx[0] + 15, ov_cx[1] + 10)
            cyst_radius = (65, 50)
            cv2.ellipse(mask, cyst_center, cyst_radius, 15, 0, 360, 255, -1)
            # Make cyst internal dark
            cv2.ellipse(us_img, cyst_center, cyst_radius, 15, 0, 360, 15, -1)
            # Posterior acoustic enhancement (brighter tissue underneath)
            post_enhancement = np.zeros_like(us_img)
            cv2.ellipse(post_enhancement, (cyst_center[0], cyst_center[1] + 85), (55, 30), 0, 0, 360, 45, -1)
            us_img = cv2.add(us_img, post_enhancement)

        elif lesion_type == "DERMOID":
            # Complex cystic mass with hyperechoic Rokitansky nodule & shadowing
            cyst_center = (ov_cx[0] - 10, ov_cx[1])
            cyst_radius = (75, 65)
            cv2.ellipse(mask, cyst_center, cyst_radius, -5, 0, 360, 255, -1)
            # Internal heterogeneous
            cv2.ellipse(us_img, cyst_center, cyst_radius, -5, 0, 360, 30, -1)
            # Bright dermoid plug
            plug_center = (cyst_center[0] - 25, cyst_center[1] - 20)
            cv2.circle(us_img, plug_center, 22, 210, -1)
            # Acoustic shadow behind plug
            shadow_mask = np.zeros_like(us_img)
            cv2.rectangle(shadow_mask, (plug_center[0] - 20, plug_center[1] + 20), (plug_center[0] + 20, 512), 255, -1)
            us_img = np.where(shadow_mask == 255, (us_img * 0.25).astype(np.uint8), us_img)

        elif lesion_type == "ENDOMETRIOMA":
            # Ground-glass low-level homogenous echoes
            cyst_center = (ov_cx[0] + 20, ov_cx[1] - 5)
            cyst_radius = (55, 45)
            cv2.ellipse(mask, cyst_center, cyst_radius, 25, 0, 360, 255, -1)
            # Homogeneous low-level echoes inside
            internal_echo = np.random.normal(loc=55, scale=8, size=(512, 512)).astype(np.uint8)
            us_img = np.where(mask == 255, internal_echo, us_img)

        # Save Image & Mask
        img_path = os.path.join(output_dir, f"{name}.png")
        mask_path = os.path.join(output_dir, f"{name}_mask.png")
        cv2.imwrite(img_path, us_img)
        cv2.imwrite(mask_path, mask)
        print(f"Generated {img_path} and {mask_path} ({desc})")


if __name__ == "__main__":
    create_sample_dataset()
