"""Deleting a case must not remove source data before durable DB success."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.routers import cases


class QueryResult:
    def __init__(self, study):
        self.study = study

    def filter(self, *_args):
        return self

    def first(self):
        return self.study


class CaseSession:
    def __init__(self, path: Path, fail_commit=False):
        self.study = SimpleNamespace(images=[SimpleNamespace(raw_path=str(path))])
        self.fail_commit = fail_commit

    def query(self, _model):
        return QueryResult(self.study)

    def delete(self, _study):
        pass

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("simulated commit failure")


def test_delete_preserves_upload_when_database_commit_fails(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)
    with pytest.raises(RuntimeError, match="commit failure"):
        cases.delete_case("study", db=CaseSession(image, fail_commit=True))
    assert image.exists()


def test_delete_never_removes_file_outside_upload_directory(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    external = tmp_path / "source.png"
    external.write_bytes(b"source")
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)
    result = cases.delete_case("study", db=CaseSession(external))
    assert result["status"] == "SUCCESS"
    assert external.exists()


def test_delete_removes_owned_upload_after_database_commit(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)
    result = cases.delete_case("study", db=CaseSession(image))
    assert result["status"] == "SUCCESS"
    assert not image.exists()
