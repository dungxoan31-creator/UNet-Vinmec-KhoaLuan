import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest

from ai_training.train_baseline_unet import validate_training_split_identity
from tests.patient_split_fixture import attach_source_identity_evidence


def _write_splits(root, patient_ids, manifest, image_hashes=None):
    root.mkdir(parents=True)
    for split, ids in patient_ids.items():
        requested_hashes = (image_hashes or {}).get(split, [])
        rows = []
        for index, patient_id in enumerate(ids):
            requested_hash = requested_hashes[index] if index < len(requested_hashes) else f"{split}-{index}"
            pixel = np.resize(np.frombuffer(hashlib.sha256(requested_hash.encode()).digest(), dtype=np.uint8), (24, 32))
            encoded, image_buffer = cv2.imencode(".png", pixel)
            assert encoded
            image_bytes = image_buffer.tobytes()
            image_path = root / "images" / f"{split}-{index}.png"
            mask_path = root / "masks" / f"{split}-{index}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            mask_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(image_bytes)
            assert cv2.imwrite(str(mask_path), np.zeros((24, 32), dtype=np.uint8))
            rows.append({
                "patient_id": patient_id,
                "case_id": f"{split}-{index}",
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
                "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
            })
        pd.DataFrame(rows).to_csv(root / f"{split}.csv", index=False)
    manifest = dict(manifest)
    if manifest.get("patient_ids_verified") is True:
        manifest.setdefault("source_patient_identity_verified", True)
    manifest.setdefault("split_counts", {split: len(ids) for split, ids in patient_ids.items()})
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if manifest.get("source_patient_identity_verified") is True:
        attach_source_identity_evidence(root)


def test_legacy_image_level_training_override_is_rejected(tmp_path, monkeypatch):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": [""], "val": [""], "test": [""]},
        {"identity_limit": "No verified source Patient/Case IDs; split is image-level only"},
    )

    with pytest.raises(TypeError, match="allow_image_level"):
        validate_training_split_identity(splits, allow_image_level=True)

    from ai_training.train_baseline_unet import train_baseline

    monkeypatch.setattr(
        "ai_training.train_baseline_unet.get_train_val_dataloaders",
        lambda **_kwargs: pytest.fail("Image-level split reached dataset loading"),
    )
    output = tmp_path / "checkpoint-output"
    with pytest.raises(TypeError, match="allow_image_level"):
        train_baseline(splits_dir=splits, checkpoint_dir=output, allow_image_level=True)
    assert not output.exists()


def test_refinement_rejects_image_level_split_before_reading_checkpoint(tmp_path, monkeypatch):
    from scripts import refine_unified_vinmec_unet as refinement

    split_dir = tmp_path / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    split_dir.mkdir(parents=True)
    (split_dir / "manifest.json").write_text(
        json.dumps({"identity_limit": "No verified source Patient/Case IDs"}), encoding="utf-8"
    )
    split_hashes = {}
    for split in ("train", "val", "test"):
        csv_path = split_dir / f"{split}.csv"
        csv_path.write_text("image_path,mask_path,image_sha256\n", encoding="utf-8")
        split_hashes[split] = hashlib.sha256(csv_path.read_bytes()).hexdigest()

    baseline_dir = tmp_path / "checkpoints/unified_vinmec_2026-10-06"
    baseline_dir.mkdir(parents=True)
    checkpoint = baseline_dir / "baseline.pth"
    checkpoint.write_bytes(b"checkpoint")
    (baseline_dir / "run_config.json").write_text(
        json.dumps(
            {
                "split_sha256": split_hashes,
                "checkpoint_best": checkpoint.relative_to(tmp_path).as_posix(),
                "best_validation_dice": 0.5,
            }
        ),
        encoding="utf-8",
    )

    real_file_sha256 = refinement.file_sha256

    def reject_checkpoint_read(path):
        if Path(path).resolve() == checkpoint.resolve():
            raise AssertionError("The split identity gate must run before reading a checkpoint")
        return real_file_sha256(path)

    monkeypatch.setattr(refinement, "file_sha256", reject_checkpoint_read)
    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        refinement.run_refinement(tmp_path)


def test_baseline_rejects_source_image_mask_shape_mismatch_before_output(tmp_path, monkeypatch):
    from ai_training.train_baseline_unet import train_baseline

    splits = tmp_path / "verified-splits"
    splits.mkdir()
    rows_by_split = {}
    for index, split in enumerate(("train", "val", "test"), start=1):
        image_path = splits / f"{split}.png"
        mask_path = splits / f"{split}-mask.png"
        image = np.full((24, 32), 40 + index, dtype=np.uint8)
        mask = np.zeros((12, 16) if split == "train" else image.shape, dtype=np.uint8)
        assert cv2.imwrite(str(image_path), image)
        assert cv2.imwrite(str(mask_path), mask)
        rows_by_split[split] = [{
            "case_id": split,
            "patient_id": f"patient-{split}",
            "image_path": str(image_path),
            "mask_path": str(mask_path),
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
        }]
        pd.DataFrame(rows_by_split[split]).to_csv(splits / f"{split}.csv", index=False)
    (splits / "manifest.json").write_text(
        json.dumps({
            "patient_ids_verified": True,
            "source_patient_identity_verified": True,
            "split_counts": {split: 1 for split in rows_by_split},
        }),
        encoding="utf-8",
    )
    attach_source_identity_evidence(splits)
    monkeypatch.setattr(
        "ai_training.train_baseline_unet.get_train_val_dataloaders",
        lambda **_kwargs: pytest.fail("Mismatched source pair reached dataset loading"),
    )
    output = tmp_path / "checkpoint-output"

    with pytest.raises(ValueError, match="(?i)image/mask dimensions differ"):
        train_baseline(splits_dir=splits, checkpoint_dir=output)

    assert not output.exists()


def test_verified_split_rejects_unreadable_source_mask(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    mask_path = Path(pd.read_csv(splits / "train.csv").iloc[0]["mask_path"])
    mask_path.write_bytes(b"corrupt mask bytes")
    train_csv = pd.read_csv(splits / "train.csv")
    train_csv.loc[0, "mask_sha256"] = hashlib.sha256(mask_path.read_bytes()).hexdigest()
    train_csv.to_csv(splits / "train.csv", index=False)

    with pytest.raises(ValueError, match="(?i)source mask is unreadable"):
        validate_training_split_identity(splits)


def test_baseline_rejects_nonbinary_mask_before_output(tmp_path, monkeypatch):
    from ai_training.train_baseline_unet import train_baseline

    splits = tmp_path / "verified-splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    train_row = pd.read_csv(splits / "train.csv").iloc[0]
    assert cv2.imwrite(str(train_row["mask_path"]), np.full((24, 32), 42, dtype=np.uint8))
    train_csv = pd.read_csv(splits / "train.csv")
    train_csv.loc[0, "mask_sha256"] = hashlib.sha256(Path(train_row["mask_path"]).read_bytes()).hexdigest()
    train_csv.to_csv(splits / "train.csv", index=False)
    monkeypatch.setattr(
        "ai_training.train_baseline_unet.get_train_val_dataloaders",
        lambda **_kwargs: pytest.fail("Invalid mask reached dataset loading"),
    )
    output = tmp_path / "checkpoint-output"

    with pytest.raises(ValueError, match="(?i)non-binary pixel values"):
        train_baseline(splits_dir=splits, checkpoint_dir=output)

    assert not output.exists()


def test_baseline_blocks_unverified_split_before_creating_checkpoint_directory(tmp_path):
    from ai_training.train_baseline_unet import train_baseline

    splits = tmp_path / "unverified-splits"
    splits.mkdir()
    (splits / "manifest.json").write_text(
        json.dumps({"identity_limit": "Source patient IDs unavailable"}), encoding="utf-8"
    )
    output = tmp_path / "checkpoint-output"

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        train_baseline(splits_dir=splits, checkpoint_dir=output)

    assert not output.exists()


def test_baseline_blocks_checkpoint_without_provenance_before_creating_output(tmp_path):
    from ai_training.train_baseline_unet import train_baseline

    splits = tmp_path / "verified-splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    checkpoint = tmp_path / "unverified-checkpoint.pth"
    checkpoint.write_bytes(b"weights")
    output = tmp_path / "checkpoint-output"

    with pytest.raises(ValueError, match="(?i)checkpoint provenance"):
        train_baseline(
            splits_dir=splits,
            checkpoint_dir=output,
            initial_checkpoint_path=checkpoint,
        )

    assert not output.exists()


def test_verified_patient_split_rejects_patient_overlap(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-1"]},
        {"patient_ids_verified": True},
    )

    with pytest.raises(ValueError, match="overlap"):
        validate_training_split_identity(splits)


def test_verified_patient_split_accepts_disjoint_patients(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )

    assert validate_training_split_identity(splits) == "patient_level_verified"


def test_patient_split_flags_without_source_identity_artifacts_are_not_verified(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    manifest_path = splits / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in (
        "identity_manifest_path",
        "identity_manifest_sha256",
        "source_metadata_path",
        "input_metadata_sha256",
    ):
        manifest.pop(key, None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)source identity evidence"):
        validate_training_split_identity(splits)


def test_verified_patient_split_rejects_patient_id_changed_after_split_creation(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    train_path = splits / "train.csv"
    train_rows = pd.read_csv(train_path)
    train_rows.loc[0, "patient_id"] = "FORGED-PATIENT"
    train_rows.to_csv(train_path, index=False)

    with pytest.raises(ValueError, match="(?i)patient_id.*source metadata"):
        validate_training_split_identity(splits)


@pytest.mark.parametrize(
    ("source_field", "error_pattern"),
    (("source_metadata_path", "source metadata SHA-256"), ("identity_manifest_path", "identity manifest SHA-256")),
)
def test_verified_patient_split_rejects_changed_source_identity_artifact(tmp_path, source_field, error_pattern):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    manifest = json.loads((splits / "manifest.json").read_text(encoding="utf-8"))
    source_path = Path(manifest[source_field])
    source_path.write_bytes(source_path.read_bytes() + b" ")

    with pytest.raises(ValueError, match=f"(?i){error_pattern}"):
        validate_training_split_identity(splits)


def test_verified_patient_split_rejects_hashed_synthetic_identity_attestation(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    manifest_path = splits / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity_path = Path(manifest["identity_manifest_path"])
    identity_manifest = json.loads(identity_path.read_text(encoding="utf-8"))
    identity_manifest["synthetic_patient_metadata"] = True
    identity_path.write_text(json.dumps(identity_manifest), encoding="utf-8")
    manifest["identity_manifest_sha256"] = hashlib.sha256(identity_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)identity manifest does not verify"):
        validate_training_split_identity(splits)


def test_synthetic_ids_cannot_claim_verified_source_patient_identity(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["SIM-1"], "val": ["SIM-2"], "test": ["SIM-3"]},
        {
            "patient_ids_verified": False,
            "identity_level": "patient_verified",
            "source_patient_identity_verified": False,
        },
    )

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        validate_training_split_identity(splits)


def test_verified_dataset_loader_loads_only_train_and_validation(tmp_path, monkeypatch):
    from pathlib import Path

    import ai_training.train_baseline_unet as training

    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    loaded = []

    class DatasetProbe:
        def __init__(self, csv_file, is_train=False, seed=42):
            loaded.append((Path(csv_file).name, is_train))

    monkeypatch.setattr(training, "OvarianUltrasoundDataset", DatasetProbe)
    training.load_verified_train_val_datasets(splits)

    assert loaded == [("train.csv", True), ("val.csv", False)]


def test_baseline_uses_a_train_validation_only_loader(tmp_path, monkeypatch):
    from pathlib import Path

    import ai_training.dataset_loader as dataset_loader
    import ai_training.train_baseline_unet as training

    splits = tmp_path / "verified-splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )

    class StopBeforeTraining(Exception):
        pass

    loaded = []

    class DatasetProbe:
        def __init__(self, csv_file, is_train=False, seed=42):
            loaded.append(Path(csv_file).name)

        def __len__(self):
            return 1

        def __getitem__(self, index):
            return index

    def stop_before_training(**kwargs):
        raise StopBeforeTraining

    def test_inclusive_loader(*args, **kwargs):
        raise AssertionError("baseline must not construct a test dataset")

    monkeypatch.setattr(dataset_loader, "OvarianUltrasoundDataset", DatasetProbe)
    monkeypatch.setattr(training, "StandardUNet", stop_before_training)
    monkeypatch.setattr(training, "get_dataloaders", test_inclusive_loader, raising=False)

    with pytest.raises(StopBeforeTraining):
        training.train_baseline(splits_dir=splits, checkpoint_dir=tmp_path / "output")
    assert loaded == ["train.csv", "val.csv"]


def test_verified_patient_split_rejects_a_row_without_patient_id(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1", ""], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )

    with pytest.raises(ValueError, match="(?i)empty patient_id"):
        validate_training_split_identity(splits)


def test_training_split_rejects_duplicate_image_hash_between_splits(tmp_path):
    splits = tmp_path / "splits"
    repeated_hash = "a" * 64
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
        {"train": [repeated_hash], "val": [repeated_hash], "test": ["b" * 64]},
    )

    with pytest.raises(ValueError, match="(?i)image SHA-256 overlap"):
        validate_training_split_identity(splits)


def test_verified_split_rejects_image_hash_metadata_mismatch(tmp_path):
    splits = tmp_path / "splits"
    splits.mkdir()
    shared_image = tmp_path / "same-image.bin"
    shared_image.write_bytes(b"same image bytes")
    manifest = {
        "patient_ids_verified": True,
        "source_patient_identity_verified": True,
        "split_counts": {"train": 1, "val": 1, "test": 1},
    }
    for split, image_hash in (
        ("train", hashlib.sha256(b"train-claim").hexdigest()),
        ("val", hashlib.sha256(b"val-claim").hexdigest()),
        ("test", hashlib.sha256(b"test-claim").hexdigest()),
    ):
        mask_path = tmp_path / f"{split}-mask.bin"
        mask_path.write_bytes(b"mask")
        pd.DataFrame(
            [{
                "case_id": split,
                "patient_id": f"patient-{split}",
                "image_path": str(shared_image),
                "mask_path": str(mask_path),
                "image_sha256": image_hash,
                "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
            }]
        ).to_csv(splits / f"{split}.csv", index=False)
    (splits / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    attach_source_identity_evidence(splits)

    with pytest.raises(ValueError, match="(?i)image SHA-256 does not match the source file"):
        validate_training_split_identity(splits)


def test_verified_split_rejects_mask_changed_after_hashing(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    train_row = pd.read_csv(splits / "train.csv").iloc[0]
    changed_mask = np.zeros((24, 32), dtype=np.uint8)
    changed_mask[5:15, 8:20] = 1
    assert cv2.imwrite(str(train_row["mask_path"]), changed_mask)

    with pytest.raises(ValueError, match="(?i)mask SHA-256 does not match the source file"):
        validate_training_split_identity(splits)


def test_verified_split_requires_mask_hash_column(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True},
    )
    train_path = splits / "train.csv"
    pd.read_csv(train_path).drop(columns=["mask_sha256"]).to_csv(train_path, index=False)

    with pytest.raises(ValueError, match="(?i)mask_sha256 column"):
        validate_training_split_identity(splits)


def test_verified_patient_split_rejects_malformed_counts(tmp_path):
    splits = tmp_path / "splits"
    _write_splits(
        splits,
        {"train": ["P-1"], "val": ["P-2"], "test": ["P-3"]},
        {"patient_ids_verified": True, "split_counts": None},
    )

    with pytest.raises(ValueError, match="(?i)split_counts"):
        validate_training_split_identity(splits)


def test_candidate_training_pipelines_stop_on_unverified_identity_manifest(tmp_path):
    from ai_training.finetune_2d_unet import finetune
    from ai_training.train_baseline_unet import train_baseline
    from ai_training.train_full_unet import train_full
    from ai_training.train_standard_unet_gray_imagenet_norm import train as train_standard
    from ai_training.train_unetplusplus_resnet34 import train as train_unetplusplus

    splits = tmp_path / "image-level-only"
    splits.mkdir()
    (splits / "manifest.json").write_text(
        json.dumps({"identity_limit": "No verified source Patient/Case IDs"}),
        encoding="utf-8",
    )

    checkpoint = tmp_path / "checkpoint-not-read.pth"
    output_dirs = [tmp_path / f"candidate-output-{index}" for index in range(5)]
    pipelines = (
        lambda output: train_baseline(splits_dir=splits, checkpoint_dir=output),
        lambda output: train_full(split_dir=splits, output_dir=output, epochs=1),
        lambda output: finetune(split_dir=splits, checkpoint=checkpoint, output_dir=output, epochs=1),
        lambda output: train_standard(split_dir=splits, output_dir=output, epochs=1),
        lambda output: train_unetplusplus(split_dir=splits, output_dir=output, epochs=1),
    )
    for train, output in zip(pipelines, output_dirs):
        with pytest.raises(ValueError, match="(?i)patient-level independence"):
            train(output)
        assert not output.exists()


def test_full_training_rejects_legacy_split_that_pooled_source_test(tmp_path):
    from ai_training.train_full_unet import train_full

    split_dir = tmp_path / "legacy-sample-level-split"
    split_dir.mkdir()
    for split in ("train", "val", "test"):
        (split_dir / f"{split}.csv").write_text("image_path,mask_path\n", encoding="utf-8")
    (split_dir / "manifest.json").write_text(
        json.dumps({
            "source_test_included_in_pool": True,
            "split_level": "sample-level",
            "source_patient_identity_verified": False,
            "patient_level_independence_verified": False,
        }),
        encoding="utf-8",
    )
    output_dir = tmp_path / "training-output"

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        train_full(split_dir=split_dir, output_dir=output_dir, epochs=1)

    assert not output_dir.exists()


def test_default_full_training_split_is_blocked_without_verified_patient_ids(tmp_path):
    from pathlib import Path

    from ai_training.train_full_unet import train_full

    split_dir = Path(__file__).resolve().parents[1] / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    manifest = json.loads((split_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "No verified source Patient/Case IDs" in manifest["identity_limit"]
    output_dir = tmp_path / "training-output"

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        train_full(split_dir=split_dir, output_dir=output_dir, epochs=1)

    assert not output_dir.exists()


def test_historical_307_manifest_does_not_claim_verified_patient_independence():
    manifest_path = (
        Path(__file__).resolve().parents[1]
        / "ai_training/splits/de_cuong_split_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["source_patient_identity_verified"] is False
    assert manifest["patient_level_independence_verified"] is False
    assert manifest["zero_leakage_verified"] is False
