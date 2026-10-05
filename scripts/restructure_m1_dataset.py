import os
import shutil
import sys

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Paths
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_GT = os.path.join(ROOT, "ai_training", "splits", "kltn_ground_truth_307.csv")
CSV_TRAIN = os.path.join(ROOT, "ai_training", "splits", "train.csv")
CSV_VAL = os.path.join(ROOT, "ai_training", "splits", "val.csv")
CSV_TEST = os.path.join(ROOT, "ai_training", "splits", "test.csv")

TARGET_M1_DIR = os.path.join(ROOT, "dataset", "vinmec_m1_307")
TARGET_M1_IMAGES = os.path.join(TARGET_M1_DIR, "images")
TARGET_M1_MASKS = os.path.join(TARGET_M1_DIR, "masks")

BACKUP_DIR = os.path.join(ROOT, "dataset_backup_archive")

os.makedirs(TARGET_M1_IMAGES, exist_ok=True)
os.makedirs(TARGET_M1_MASKS, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

df_gt = pd.read_csv(CSV_GT)

m1_old_to_new = {}

print("Step 1: Copying/organizing 307 Moc 1 images and masks into dataset/vinmec_m1_307/...")

for idx, row in df_gt.iterrows():
    img_old = row['image_path'].replace('\\', '/')
    mask_old = row['mask_path'].replace('\\', '/')

    img_old_full = os.path.join(ROOT, img_old.replace('/', os.sep))
    mask_old_full = os.path.join(ROOT, mask_old.replace('/', os.sep))

    filename_img = f"{idx+1:03d}_{os.path.basename(img_old)}"
    filename_mask = f"{idx+1:03d}_{os.path.basename(mask_old)}"
    if not filename_mask.endswith('.png'):
        filename_mask = os.path.splitext(filename_mask)[0] + '.png'

    img_new_rel = f"dataset/vinmec_m1_307/images/{filename_img}"
    mask_new_rel = f"dataset/vinmec_m1_307/masks/{filename_mask}"

    img_new_full = os.path.join(ROOT, img_new_rel.replace('/', os.sep))
    mask_new_full = os.path.join(ROOT, mask_new_rel.replace('/', os.sep))

    shutil.copy2(img_old_full, img_new_full)
    shutil.copy2(mask_old_full, mask_new_full)

    m1_old_to_new[img_old] = img_new_rel
    m1_old_to_new[mask_old] = mask_new_rel

print(f"Copied {len(df_gt)} image-mask pairs to vinmec_m1_307.")

print("Step 2: Updating CSV split files...")

def update_csv(csv_path):
    df = pd.read_csv(csv_path)
    df['image_path'] = df['image_path'].apply(lambda x: m1_old_to_new.get(x.replace('\\', '/'), x))
    df['mask_path'] = df['mask_path'].apply(lambda x: m1_old_to_new.get(x.replace('\\', '/'), x))
    df.to_csv(csv_path, index=False)
    print(f"Updated {csv_path}")

update_csv(CSV_GT)
update_csv(CSV_TRAIN)
update_csv(CSV_VAL)
update_csv(CSV_TEST)

print("Step 3: Moving remaining unused dataset directories to dataset_backup_archive/...")

dataset_root = os.path.join(ROOT, "dataset")
items_to_move = ["Vinmec", "Vinmec_2D", "Vinmec_CEUS", "vinmec_ovarian"]

for item in items_to_move:
    src = os.path.join(dataset_root, item)
    dst = os.path.join(BACKUP_DIR, item)
    if os.path.exists(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.move(src, dst)
        print(f"Moved {item} -> dataset_backup_archive/{item}")

print("DATA REORGANIZATION COMPLETE SUCCESSFULLY!")
