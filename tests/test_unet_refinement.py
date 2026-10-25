import pytest

from scripts.refine_unified_vinmec_unet import select_best_candidate, verify_split_hashes


def test_refinement_requires_the_frozen_split_hashes(tmp_path):
    for name in ("train", "val", "test"):
        (tmp_path / f"{name}.csv").write_text(name, encoding="utf-8")
    expected = {name: "unchanged" for name in ("train", "val", "test")}

    with pytest.raises(ValueError, match="split SHA-256 mismatch"):
        verify_split_hashes(tmp_path, expected)


def test_candidate_selection_uses_validation_dice_and_keeps_incumbent_on_tie():
    incumbent = {"checkpoint_best": "baseline.pth", "best_validation_dice": 0.63}
    runs = [
        {"name": "lr_1e-4", "checkpoint_best": "low.pth", "best_validation_dice": 0.64},
        {"name": "lr_3e-4", "checkpoint_best": "high.pth", "best_validation_dice": 0.63},
    ]

    result = select_best_candidate(incumbent, runs)

    assert result["selected"]["name"] == "lr_1e-4"
    assert result["validation_only_selection"] is True
    assert result["test_used_for_selection"] is False
