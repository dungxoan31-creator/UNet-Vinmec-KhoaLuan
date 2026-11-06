import sys

import cv2
import numpy as np
import pytest
import torch

import ai_training.train_classifier_8class as classifier


def test_mmotu_class_ids_follow_global_category_annotation_order():
    assert classifier.MMOTU_8_CLASSES == (
        "chocolate_cyst",
        "serous_cystadenoma",
        "teratoma",
        "theca_cell_tumor",
        "simple_cyst",
        "normal_ovary",
        "mucinous_cystadenoma",
        "high_grade_serous_cystadenocarcinoma",
    )


def test_build_classifier_model_accepts_color_images():
    model = classifier.build_classifier_model(pretrained=False)
    output = model(torch.randn(2, 3, 64, 64))
    assert output.shape == (2, 8)


def test_compute_multiclass_metrics_returns_per_class_results_without_malignancy_claims():
    logits = torch.zeros((8, 8))
    logits[torch.arange(8), torch.arange(8)] = 5.0
    metrics = classifier.compute_multiclass_metrics(logits, torch.arange(8))

    assert metrics["accuracy"] == 1.0
    assert metrics["macro_f1"] == 1.0
    assert metrics["balanced_accuracy"] == 1.0
    assert metrics["per_class"]["normal_ovary"]["recall"] == 1.0
    assert metrics["sample_count"] == 8
    assert "malignant_sensitivity" not in metrics


def _make_color_images(images_dir, count=8):
    images_dir.mkdir(parents=True)
    for index in range(count):
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        image[:, :, index % 3] = 30 + index * 20
        assert cv2.imwrite(str(images_dir / f"{index + 1}.JPG"), image)


def test_parse_class_labels_reads_official_filename_id_format_and_hashes_images(tmp_path):
    images_dir = tmp_path / "images"
    _make_color_images(images_dir)
    labels = tmp_path / "labels.txt"
    labels.write_text("1.JPG 0\n2.JPG 1\n", encoding="utf-8")

    records = classifier.parse_class_labels(labels, images_dir)

    assert [record["label_name"] for record in records] == ["chocolate_cyst", "serous_cystadenoma"]
    assert all(len(record["image_sha256"]) == 64 for record in records)


@pytest.mark.parametrize("line", ["1.JPG 8", "../1.JPG 0", "1.JPG nope", "1.JPG 0 extra"])
def test_parse_class_labels_rejects_invalid_entries(tmp_path, line):
    images_dir = tmp_path / "images"
    _make_color_images(images_dir)
    labels = tmp_path / "labels.txt"
    labels.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        classifier.parse_class_labels(labels, images_dir)


def test_parse_class_labels_rejects_missing_labeled_images(tmp_path):
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    labels = tmp_path / "labels.txt"
    labels.write_text("missing.JPG 0\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="Labeled MMOTU image"):
        classifier.parse_class_labels(labels, images_dir)


def test_image_level_partition_audit_requires_unique_image_content(tmp_path):
    train_records = [
        {"image_id": f"{index + 1}.JPG", "image_sha256": str(index), "label": index}
        for index in range(8)
    ]
    val_records = [
        {"image_id": f"val_{index + 1}.JPG", "image_sha256": f"val_{index}", "label": index}
        for index in range(8)
    ]
    audit = classifier.validate_image_level_partitions(train_records, val_records)
    assert audit["split_level"] == "image-level"
    assert audit["patient_level_independence_verified"] is False

    duplicate_image = dict(train_records[0], image_id="copy.JPG")
    with pytest.raises(ValueError, match="image-content overlap"):
        classifier.validate_image_level_partitions(train_records, [duplicate_image, *val_records[1:]])


def test_dataset_preserves_three_channels_and_reports_label(tmp_path):
    images_dir = tmp_path / "images"
    _make_color_images(images_dir)
    records = classifier.parse_class_labels(
        _write_labels(tmp_path, "1.JPG 7\n"), images_dir
    )
    sample = classifier.MMOTUClassificationDataset(records, image_size=64)[0]

    assert sample["image"].shape == (3, 64, 64)
    assert sample["target"].item() == 7
    assert sample["image_id"] == "1.JPG"


def _write_labels(tmp_path, contents):
    labels = tmp_path / "labels.txt"
    labels.write_text(contents, encoding="utf-8")
    return labels


def test_classifier_cli_passes_image_level_training_configuration(monkeypatch, tmp_path):
    captured = {}

    def fake_train_classifier(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(classifier, "train_classifier", fake_train_classifier)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_classifier_8class.py",
            "--images-dir",
            str(tmp_path / "images"),
            "--train-labels",
            str(tmp_path / "train.txt"),
            "--val-labels",
            str(tmp_path / "val.txt"),
            "--epochs",
            "1",
            "--selection-metric",
            "accuracy",
            "--freeze-encoder",
            "--no-pretrained",
        ],
    )

    classifier.main()

    assert captured["epochs"] == 1
    assert captured["pretrained"] is False
    assert captured["selection_metric"] == "accuracy"
    assert captured["freeze_encoder"] is True
    assert captured["train_labels"] == tmp_path / "train.txt"


def test_train_classifier_rejects_unsupported_selection_metric_before_loading_data(tmp_path):
    with pytest.raises(ValueError, match="selection_metric"):
        classifier.train_classifier(
            images_dir=tmp_path / "missing-images",
            train_labels=tmp_path / "missing-train.txt",
            val_labels=tmp_path / "missing-val.txt",
            output_dir=tmp_path / "output",
            epochs=1,
            selection_metric="precision",
        )
