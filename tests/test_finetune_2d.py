import csv
from pathlib import Path

from ai_training.finetune_2d_unet import select_2d_rows


def test_select_2d_rows_excludes_ceus_and_keeps_both_2d_groups(tmp_path: Path):
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("case_id", "image_path", "mask_path"))
        writer.writerow(("Vinmec_2D_train_1", "a.JPG", "a.PNG"))
        writer.writerow(("Vinmec_2D_test_2", "b.JPG", "b.PNG"))
        writer.writerow(("Vinmec_CEUS_3", "c.JPG", "c.PNG"))

    assert [row["case_id"] for row in select_2d_rows(manifest)] == ["Vinmec_2D_train_1", "Vinmec_2D_test_2"]
