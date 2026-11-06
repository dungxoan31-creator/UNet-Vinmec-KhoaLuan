from backend.core.dataset_paths import resolve_dataset_path


def test_relocated_image_and_mask_paths_resolve_using_synthetic_files(tmp_path):
    image = tmp_path / "dataset/2d/images/synthetic_left.png"
    mask = tmp_path / "dataset/2d/masks/synthetic_left_binary.PNG"
    image.parent.mkdir(parents=True)
    mask.parent.mkdir(parents=True)
    image.write_bytes(b"synthetic-image-fixture")
    mask.write_bytes(b"synthetic-mask-fixture")

    assert resolve_dataset_path(tmp_path, "dataset/Vinmec/Vinmec_2d/images/synthetic_left.png") == image
    assert resolve_dataset_path(tmp_path, "dataset/Vinmec/Vinmec_2d/annotations/synthetic_left_binary.PNG") == mask
    assert image.read_bytes().startswith(b"synthetic-")
    assert mask.read_bytes().startswith(b"synthetic-")


def test_relocated_dataset_directories_resolve_to_canonical_roots(tmp_path):
    assert resolve_dataset_path(tmp_path, "dataset/Vinmec/Vinmec_2d/images") == tmp_path / "dataset/2d/images"
    assert resolve_dataset_path(tmp_path, "dataset/Vinmec/Vinmec_2d/annotations") == tmp_path / "dataset/2d/masks"
    assert resolve_dataset_path(tmp_path, "dataset/Vinmec/Vinmec_3d/images") == tmp_path / "dataset/3d/images"
    assert resolve_dataset_path(tmp_path, "dataset/Vinmec/Vinmec_3d/annotations") == tmp_path / "dataset/3d/masks"


def test_relocated_3d_binary_mask_keeps_canonical_filename(tmp_path):
    mask = tmp_path / "dataset/3d/masks/synthetic_right.PNG"
    mask.parent.mkdir(parents=True)
    mask.write_bytes(b"synthetic-mask-fixture")

    assert resolve_dataset_path(tmp_path, "dataset/Vinmec/Vinmec_3d/annotations/synthetic_right_binary.PNG") == mask


def test_missing_historical_mask_remains_missing_and_unrelated_path_is_not_remapped(tmp_path):
    missing = resolve_dataset_path(tmp_path, "dataset/vinmec_ovarian/empty_masks/empty_mask_001.png")
    unrelated = resolve_dataset_path(tmp_path, "dataset/other/images/synthetic.png")
    assert not missing.exists()
    assert unrelated == tmp_path / "dataset/other/images/synthetic.png"
