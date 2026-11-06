"""Guardrail tests for the staged research training pipeline."""

import pytest
import torch

from ai_training import train_multi_source_boosted as pipeline


def test_vinmec_legacy_alias_cannot_resolve_to_mmotu(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    alias_target = tmp_path / "dataset/2d/images/1168.JPG"
    alias_target.parent.mkdir(parents=True)
    alias_target.write_bytes(b"MMOTU image")

    # The legacy resolver maps Vinmec paths to dataset/2d, but source-strict
    # validation must reject that alias as evidence of Vinmec provenance.
    assert pipeline._project_path("dataset/Vinmec/Vinmec_2d/images/1168.JPG") == alias_target
    with pytest.raises(FileNotFoundError, match="Legacy path aliases are not accepted"):
        pipeline._source_specific_path("dataset/Vinmec/Vinmec_2d/images/1168.JPG", "Vinmec image")


def test_advanced_hybrid_loss_is_finite_and_differentiable():
    logits = torch.zeros((2, 1, 16, 16), requires_grad=True)
    targets = torch.zeros_like(logits)
    targets[:, :, 4:10, 5:11] = 1

    loss = pipeline.AdvancedHybridLoss()(logits, targets)
    loss.backward()

    assert torch.isfinite(loss)
    assert logits.grad is not None
    assert torch.isfinite(logits.grad).all()
