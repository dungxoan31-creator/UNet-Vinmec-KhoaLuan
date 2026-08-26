"""
Generates 24 visual sample previews across OTU_2D (Train & Test) and OTU_CEUS.
Each preview contains: Original Image, Ground Truth Mask, and Overlay.
"""

import glob
import os

import cv2
import numpy as np

DATASET_ROOT = os.path.abspath(r"c:\Users\PeaceD_Dung\Documents\Khóa luận\dataset\dataset")
PREVIEW_DIR = os.path.abspath(r"c:\Users\PeaceD_Dung\Documents\Khóa luận\ai_training\dataset_preview")
os.makedirs(PREVIEW_DIR, exist_ok=True)


def cv2_imread_unicode(file_path, flags=cv2.IMREAD_COLOR):
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)


def cv2_imwrite_unicode(file_path, img_np):
    ext = os.path.splitext(file_path)[1]
    ret, buf = cv2.imencode(ext, img_np)
    if ret:
        with open(file_path, "wb") as f:
            f.write(buf)


def generate_samples():
    subsets = [
        (
            "OTU_2D_train",
            os.path.join(DATASET_ROOT, "OTU_2D", "train", "train_image"),
            os.path.join(DATASET_ROOT, "OTU_2D", "train", "train_label", "label"),
            12,
        ),
        (
            "OTU_2D_test",
            os.path.join(DATASET_ROOT, "OTU_2D", "test", "image"),
            os.path.join(DATASET_ROOT, "OTU_2D", "test", "label", "black_write"),
            8,
        ),
        (
            "OTU_CEUS",
            os.path.join(DATASET_ROOT, "OTU_CEUS", "image"),
            os.path.join(DATASET_ROOT, "OTU_CEUS", "label"),
            4,
        ),
    ]

    count = 0
    for subset_name, img_dir, mask_dir, num_samples in subsets:
        img_files = sorted(glob.glob(os.path.join(img_dir, "*.*")), key=lambda x: os.path.basename(x))
        # Select evenly spaced samples
        step = max(1, len(img_files) // num_samples)
        selected_imgs = img_files[::step][:num_samples]

        for img_path in selected_imgs:
            count += 1
            base = os.path.splitext(os.path.basename(img_path))[0]
            mask_path = os.path.join(mask_dir, f"{base}.PNG")
            if not os.path.exists(mask_path):
                mask_path = os.path.join(mask_dir, f"{base}.png")

            img_np = cv2_imread_unicode(img_path, cv2.IMREAD_COLOR)
            mask_np = cv2_imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)

            if img_np is None or mask_np is None:
                continue

            h, w = img_np.shape[:2]
            # Standardize view to 400x400
            disp_h, disp_w = 400, 400
            p1 = cv2.resize(img_np, (disp_w, disp_h))

            # Mask visual
            mask_disp = cv2.resize(mask_np, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)
            p2 = cv2.cvtColor(mask_disp, cv2.COLOR_GRAY2BGR)

            # Overlay visual
            mask_binary = (mask_disp > 127).astype(np.uint8)
            p3 = p1.copy()
            # Red tint on lesion
            p3[mask_binary == 1] = cv2.addWeighted(
                p1[mask_binary == 1], 0.35, np.full_like(p1[mask_binary == 1], (0, 0, 255)), 0.65, 0
            )
            # Green contour
            contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(p3, contours, -1, (0, 255, 0), 2)

            # Labels
            cv2.putText(
                p1,
                f"ORIGINAL: {os.path.basename(img_path)} ({w}x{h})",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
            cv2.putText(p2, "GROUND TRUTH MASK (OTU GT)", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(p3, f"OVERLAY [{subset_name}]", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            combined = np.hstack([p1, p2, p3])
            out_file = os.path.join(PREVIEW_DIR, f"sample_{count:03d}_{subset_name}_{base}.png")
            cv2_imwrite_unicode(out_file, combined)

    print(f"[Done] Generated {count} visual audit previews in ai_training/dataset_preview/")


if __name__ == "__main__":
    generate_samples()
