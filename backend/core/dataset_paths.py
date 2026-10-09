"""Resolve recorded dataset paths after the October directory reorganization."""

from pathlib import Path


def resolve_dataset_path(root: Path, recorded: str) -> Path:
    relative = recorded.replace("\\", "/")
    original = root / relative
    if original.is_file():
        return original

    parts = relative.split("/")
    if len(parts) < 4 or parts[0] != "dataset":
        return original
    source = "/".join(parts[1:-1])
    name = parts[-1]
    if source in {"Vinmec/Vinmec_2d/images", "Vinmec_2D/train/train_image", "Vinmec_2D/test/image"}:
        return root / "dataset/2d/images" / name
    if source in {"Vinmec/Vinmec_2d/annotations", "Vinmec_2D/train/train_label/label", "Vinmec_2D/test/label/black_write"}:
        return root / "dataset/2d/masks" / name
    if source == "Vinmec/Vinmec_3d/images":
        return root / "dataset/3d/images" / name
    if source == "Vinmec/Vinmec_3d/annotations":
        # The retained masks are the CEUS copies whose binary pixels were
        # compared with these canonical labels in the frozen provenance audit.
        return root / "dataset/3d/masks" / (name.removesuffix("_binary.PNG") + ".PNG")
    return original
