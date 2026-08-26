"""
Rich Ovarian Ultrasound Dataset Generator & Augmentation Pipeline:
Generates a comprehensive dataset of 120 realistic clinical ultrasound cases:
- Category 1: Simple Serous Cysts (Anechoic, thin smooth wall, posterior enhancement)
- Category 2: Dermoid Cysts / Mature Teratoma (Hyperechoic Rokitansky nodule + shadow)
- Category 3: Endometriomas / Chocolate Cysts (Homogeneous ground-glass echoes)
- Category 4: Hemorrhagic Cysts (Spiderweb/fishnet reticular fibrin strands)
- Category 5: Normal Ovaries (Empty Mask - True Negative controls)
"""

import os
import random

import cv2
import numpy as np

DATASET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "ovarian_dataset"))


def cv2_imwrite_unicode(file_path, img_np):
    ext = os.path.splitext(file_path)[1]
    ret, buf = cv2.imencode(ext, img_np)
    if ret:
        with open(file_path, "wb") as f:
            f.write(buf)


def generate_ultrasound_base(h=512, w=512, seed=None):
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    canvas = np.zeros((h, w), dtype=np.uint8)
    apex = (w // 2 + random.randint(-15, 15), 35 + random.randint(-10, 10))
    radius = random.randint(420, 450)
    start_angle = random.randint(30, 38)
    end_angle = random.randint(142, 150)

    # Active scanning sector
    cv2.ellipse(canvas, apex, (radius, radius), 0, start_angle, end_angle, 100, -1)

    # Rayleight/Gaussian speckle noise with depth attenuation
    base_speckle = np.random.normal(loc=55, scale=22, size=(h, w)).astype(np.float32)
    y_coords, x_coords = np.indices((h, w))
    dist = np.sqrt((x_coords - apex[0]) ** 2 + (y_coords - apex[1]) ** 2)
    attenuation = np.clip(1.0 - (dist / 550.0) * 0.35, 0.45, 1.0)

    tissue = (base_speckle * attenuation).astype(np.uint8)
    tissue_masked = cv2.bitwise_and(tissue, tissue, mask=canvas)

    # Ovary stroma location
    ov_cx = w // 2 + random.randint(-35, 35)
    ov_cy = 260 + random.randint(-30, 30)
    ov_axes = (random.randint(125, 155), random.randint(85, 110))
    ov_angle = random.randint(-20, 20)

    ovary_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(ovary_mask, (ov_cx, ov_cy), ov_axes, ov_angle, 0, 360, 255, -1)

    # Brighter stroma speckle
    stroma_speckle = np.random.normal(loc=82, scale=18, size=(h, w)).astype(np.uint8)
    tissue_masked = np.where(ovary_mask == 255, stroma_speckle, tissue_masked)

    # Add ultrasound sector outline
    cv2.ellipse(tissue_masked, apex, (radius, radius), 0, start_angle, end_angle, 160, 2)

    return tissue_masked, (ov_cx, ov_cy), ov_axes, ov_angle


def build_full_dataset(num_patients=60, images_per_patient=2):
    os.makedirs(DATASET_DIR, exist_ok=True)
    print(
        f"[Data Pipeline] Generating {num_patients * images_per_patient} clinical ultrasound cases in data/ovarian_dataset..."
    )

    lesion_types = ["NORMAL", "SIMPLE_CYST", "DERMOID", "ENDOMETRIOMA", "HEMORRHAGIC"]
    # 20% Normal (Empty Mask), 80% with lesions
    weights = [0.20, 0.25, 0.20, 0.20, 0.15]

    total_images = 0
    empty_masks = 0

    for pid in range(1, num_patients + 1):
        patient_str = f"PATIENT_{pid:03d}"
        chosen_type = random.choices(lesion_types, weights=weights)[0]

        for img_idx in range(1, images_per_patient + 1):
            seed = pid * 100 + img_idx
            us_img, ov_center, _ov_axes, _ov_angle = generate_ultrasound_base(512, 512, seed=seed)
            mask = np.zeros((512, 512), dtype=np.uint8)

            if chosen_type == "NORMAL":
                # Multiple tiny normal follicles (<8mm)
                for _ in range(random.randint(3, 6)):
                    fc = (ov_center[0] + random.randint(-40, 40), ov_center[1] + random.randint(-30, 30))
                    cv2.circle(us_img, fc, random.randint(6, 12), random.randint(15, 30), -1)
                empty_masks += 1

            elif chosen_type == "SIMPLE_CYST":
                c_center = (ov_center[0] + random.randint(-20, 20), ov_center[1] + random.randint(-15, 15))
                c_axes = (random.randint(45, 80), random.randint(40, 70))
                c_ang = random.randint(0, 45)
                cv2.ellipse(mask, c_center, c_axes, c_ang, 0, 360, 255, -1)
                # Internal anechoic dark fluid
                cv2.ellipse(us_img, c_center, c_axes, c_ang, 0, 360, random.randint(8, 20), -1)
                # Posterior acoustic enhancement
                post_enh = np.zeros_like(us_img)
                cv2.ellipse(
                    post_enh, (c_center[0], c_center[1] + c_axes[1] + 25), (c_axes[0] - 10, 35), 0, 0, 360, 40, -1
                )
                us_img = cv2.add(us_img, post_enh)

            elif chosen_type == "DERMOID":
                c_center = (ov_center[0] + random.randint(-25, 25), ov_center[1] + random.randint(-20, 20))
                c_axes = (random.randint(55, 85), random.randint(50, 75))
                c_ang = random.randint(-30, 30)
                cv2.ellipse(mask, c_center, c_axes, c_ang, 0, 360, 255, -1)
                # Heterogeneous interior
                cv2.ellipse(us_img, c_center, c_axes, c_ang, 0, 360, random.randint(25, 45), -1)
                # Bright Rokitansky plug
                plug_c = (c_center[0] + random.randint(-20, 20), c_center[1] + random.randint(-20, 10))
                cv2.circle(us_img, plug_c, random.randint(18, 26), random.randint(190, 230), -1)
                # Dense acoustic shadow behind plug
                shadow = np.zeros_like(us_img)
                cv2.rectangle(shadow, (plug_c[0] - 18, plug_c[1] + 15), (plug_c[0] + 18, 512), 255, -1)
                us_img = np.where(shadow == 255, (us_img * 0.25).astype(np.uint8), us_img)

            elif chosen_type == "ENDOMETRIOMA":
                c_center = (ov_center[0] + random.randint(-20, 20), ov_center[1] + random.randint(-15, 15))
                c_axes = (random.randint(45, 75), random.randint(35, 65))
                c_ang = random.randint(-20, 20)
                cv2.ellipse(mask, c_center, c_axes, c_ang, 0, 360, 255, -1)
                # Homogeneous low-level echoes
                echoes = np.random.normal(loc=52, scale=7, size=(512, 512)).astype(np.uint8)
                us_img = np.where(mask == 255, echoes, us_img)

            elif chosen_type == "HEMORRHAGIC":
                c_center = (ov_center[0] + random.randint(-20, 20), ov_center[1] + random.randint(-15, 15))
                c_axes = (random.randint(50, 75), random.randint(40, 65))
                c_ang = random.randint(-15, 15)
                cv2.ellipse(mask, c_center, c_axes, c_ang, 0, 360, 255, -1)
                # Internal fluid
                cv2.ellipse(us_img, c_center, c_axes, c_ang, 0, 360, 22, -1)
                # Reticular spiderweb fibrin strands
                for _ in range(12):
                    p1 = (
                        c_center[0] + random.randint(-c_axes[0] + 15, c_axes[0] - 15),
                        c_center[1] + random.randint(-c_axes[1] + 15, c_axes[1] - 15),
                    )
                    p2 = (
                        c_center[0] + random.randint(-c_axes[0] + 15, c_axes[0] - 15),
                        c_center[1] + random.randint(-c_axes[1] + 15, c_axes[1] - 15),
                    )
                    cv2.line(us_img, p1, p2, random.randint(90, 140), 1)

            # Save File
            base_filename = f"{patient_str}_img{img_idx}_{chosen_type.lower()}"
            img_file = os.path.join(DATASET_DIR, f"{base_filename}.png")
            mask_file = os.path.join(DATASET_DIR, f"{base_filename}_mask.png")

            cv2_imwrite_unicode(img_file, us_img)
            cv2_imwrite_unicode(mask_file, mask)
            total_images += 1

    print(
        f"[Done] Generated {total_images} images across {num_patients} patients ({empty_masks} Empty Masks / True Negatives)."
    )


if __name__ == "__main__":
    build_full_dataset(num_patients=60, images_per_patient=2)
