import hashlib
import json
from pathlib import Path

from backend.app.config import selected_checkpoint_path


def test_selected_checkpoint_requires_matching_checksum(tmp_path):
    checkpoint = tmp_path / "vinmec_unet_best.pth"
    checkpoint.write_bytes(b"selected weights")
    manifest = tmp_path / "selected_model.json"
    manifest.write_text(
        json.dumps(
            {
                "checkpoint": str(checkpoint),
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "threshold": 0.5,
            }
        ),
        encoding="utf-8",
    )

    assert selected_checkpoint_path(manifest) == str(checkpoint)
    checkpoint.write_bytes(b"changed weights")
    assert selected_checkpoint_path(manifest) is None


def test_prototype_uses_validation_selected_checkpoint_with_matching_sha():
    root = Path(__file__).resolve().parents[1]
    manifest = root / "evaluation/selected_model.json"
    selection = json.loads(manifest.read_text(encoding="utf-8"))
    checkpoint = root / selection["checkpoint"]
    test_summary = json.loads(
        (root / selection["test_evaluation"]["summary"]).read_text(encoding="utf-8")
    )

    assert selection["selection_split"] == "val"
    assert selection["selection_count"] == 541
    assert selection["threshold"] == 0.5
    assert checkpoint.is_file()
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == selection["checkpoint_sha256"]
    assert selected_checkpoint_path(manifest) == str(checkpoint)
    assert test_summary["checkpoint_sha256"] == selection["checkpoint_sha256"]
    assert test_summary["threshold"] == selection["threshold"]
    assert Path(root / selection["previous_selection_archive"]).is_file()
