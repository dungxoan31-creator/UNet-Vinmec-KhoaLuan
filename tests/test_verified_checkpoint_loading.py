import hashlib

import pytest
import torch


def test_checkpoint_loader_hashes_and_loads_the_same_snapshot(monkeypatch, tmp_path):
    from backend.services.inference_engine import _load_verified_checkpoint

    checkpoint = tmp_path / "selected.pth"
    original = b"selected checkpoint bytes"
    checkpoint.write_bytes(original)
    loaded_payloads = []

    def mutate_source_after_snapshot(stream, **kwargs):
        loaded_payloads.append(stream.read())
        checkpoint.write_bytes(b"changed after selection")
        return {"loaded": True}

    monkeypatch.setattr(torch, "load", mutate_source_after_snapshot)
    checksum, state_dict = _load_verified_checkpoint(
        checkpoint,
        device="cpu",
        expected_checksum=hashlib.sha256(original).hexdigest(),
    )

    assert checksum == hashlib.sha256(original).hexdigest()
    assert loaded_payloads == [original]
    assert state_dict == {"loaded": True}


def test_checkpoint_loader_rejects_hash_mismatch_before_deserialization(monkeypatch, tmp_path):
    from backend.services.inference_engine import _load_verified_checkpoint

    checkpoint = tmp_path / "tampered.pth"
    checkpoint.write_bytes(b"tampered bytes")
    called = False

    def unexpected_load(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("mismatched checkpoint must not be deserialized")

    monkeypatch.setattr(torch, "load", unexpected_load)
    with pytest.raises(ValueError, match="SHA-256"):
        _load_verified_checkpoint(checkpoint, device="cpu", expected_checksum="0" * 64)

    assert called is False
