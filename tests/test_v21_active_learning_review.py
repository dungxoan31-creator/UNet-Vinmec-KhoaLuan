import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from backend.services.review_service import (
    _resolve_active_learning_queue_path,
    log_active_learning_sample,
    remove_legacy_active_learning_samples,
)


def test_active_learning_export_uses_runtime_data_directory(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime-data"
    monkeypatch.setenv("APP_DATA_DIR", str(runtime_dir))

    assert _resolve_active_learning_queue_path() == runtime_dir / "active_learning_queue.jsonl"


def test_active_learning_export_resolves_relative_data_directory_from_project_root(tmp_path):
    assert _resolve_active_learning_queue_path(
        project_root=tmp_path,
        data_dir="isolated-runtime",
    ) == tmp_path / "isolated-runtime" / "active_learning_queue.jsonl"


def test_active_learning_export_defaults_outside_source_metadata(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_DATA_DIR", raising=False)

    assert _resolve_active_learning_queue_path(project_root=tmp_path) == (
        tmp_path / "data" / "active_learning_queue.jsonl"
    )


def _write_active_learning_batch(args):
    queue_path, process_index, sample_count = args
    import backend.services.review_service as review_service

    review_service.ACTIVE_LEARNING_QUEUE_PATH = Path(queue_path)
    for sample_index in range(sample_count):
        review_service.log_active_learning_sample(
            image_id=f"image-{process_index}-{sample_index}",
            prediction_id=f"prediction-{process_index}-{sample_index}",
            doctor_action="MODIFIED",
            verified_mask_rle={"shape": [512, 512], "counts": [262144], "first_val": 0},
            lesion_type="",
        )
    return sample_count


def test_log_active_learning_sample(tmp_path, monkeypatch):
    test_queue_file = tmp_path / "test_active_learning.jsonl"
    monkeypatch.setattr(
        "backend.services.review_service.ACTIVE_LEARNING_QUEUE_PATH",
        test_queue_file,
    )

    sample = log_active_learning_sample(
        image_id="img-test-123",
        prediction_id="pred-test-456",
        doctor_action="MODIFIED",
        verified_mask_rle={"shape": [512, 512], "counts": [262144], "first_val": 0},
        lesion_type="serous_cystadenoma",
        clinician_overrides={"lesion_type": "mucinous_cystadenoma", "locules": 2},
        actor_id="dr_dung",
    )

    assert sample["image_id"] == "img-test-123"
    assert sample["doctor_action"] == "MODIFIED"
    assert sample["clinician_overrides"]["locules"] == 2

    # Verify file was written
    assert test_queue_file.exists()
    lines = test_queue_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    logged_data = json.loads(lines[0])
    assert logged_data["actor_id"] == "dr_dung"
    assert logged_data["clinician_overrides"]["lesion_type"] == "mucinous_cystadenoma"


def test_log_active_learning_sample_is_jsonl_safe_across_processes(tmp_path):
    queue_path = tmp_path / "concurrent_active_learning.jsonl"
    batches = [(str(queue_path), index, 12) for index in range(4)]
    with ProcessPoolExecutor(
        max_workers=4,
        mp_context=multiprocessing.get_context("spawn"),
    ) as executor:
        assert sum(executor.map(_write_active_learning_batch, batches)) == 48

    lines = queue_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert len(records) == 48
    assert queue_path.with_name(f"{queue_path.name}.lock").stat().st_size == 0
    assert {record["image_id"] for record in records} == {
        f"image-{process_index}-{sample_index}"
        for process_index in range(4)
        for sample_index in range(12)
    }


def test_remove_legacy_samples_fails_closed_for_malformed_lines(tmp_path, monkeypatch):
    queue_path = tmp_path / "active-learning.jsonl"
    queue_path.write_text(
        json.dumps({"image_id": "deleted-image"})
        + "\n"
        + json.dumps({"image_id": "retained-image"})
        + "\n"
        + "{malformed legacy line\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.services.review_service.ACTIVE_LEARNING_QUEUE_PATH",
        queue_path,
    )
    monkeypatch.setattr(
        "backend.services.review_service._LEGACY_ACTIVE_LEARNING_QUEUE_PATH",
        queue_path,
    )

    result = remove_legacy_active_learning_samples(["deleted-image"])

    assert result.removed_count == 0
    assert not result.complete
    assert queue_path.read_text(encoding="utf-8").splitlines() == [
        '{"image_id": "deleted-image"}',
        '{"image_id": "retained-image"}',
        "{malformed legacy line",
    ]


def test_remove_legacy_samples_prunes_runtime_and_source_tree_exports(tmp_path, monkeypatch):
    runtime_queue = tmp_path / "runtime" / "active-learning.jsonl"
    source_tree_queue = tmp_path / "source" / "active-learning.jsonl"
    runtime_queue.parent.mkdir()
    source_tree_queue.parent.mkdir()
    runtime_queue.write_text(
        '{"image_id":"deleted-image"}\n{"image_id":"runtime-retained"}\n',
        encoding="utf-8",
    )
    source_tree_queue.write_text(
        '{"image_id":"deleted-image"}\n'
        '{"image_id":"legacy-retained"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.services.review_service.ACTIVE_LEARNING_QUEUE_PATH",
        runtime_queue,
    )
    monkeypatch.setattr(
        "backend.services.review_service._LEGACY_ACTIVE_LEARNING_QUEUE_PATH",
        source_tree_queue,
    )

    result = remove_legacy_active_learning_samples(["deleted-image"])

    assert result.removed_count == 2
    assert result.complete
    assert [json.loads(line) for line in runtime_queue.read_text(encoding="utf-8").splitlines()] == [
        {"image_id": "runtime-retained"}
    ]
    source_lines = source_tree_queue.read_text(encoding="utf-8").splitlines()
    assert json.loads(source_lines[0]) == {"image_id": "legacy-retained"}


def test_remove_legacy_samples_reports_incomplete_prune(tmp_path, monkeypatch):
    runtime_queue = tmp_path / "runtime-active-learning.jsonl"
    legacy_queue = tmp_path / "legacy-active-learning.jsonl"
    runtime_queue.write_text('{"image_id":"deleted-image"}\n', encoding="utf-8")
    legacy_queue.write_text('{"image_id":"deleted-image"}\n', encoding="utf-8")
    monkeypatch.setattr(
        "backend.services.review_service.ACTIVE_LEARNING_QUEUE_PATH",
        runtime_queue,
    )
    monkeypatch.setattr(
        "backend.services.review_service._LEGACY_ACTIVE_LEARNING_QUEUE_PATH",
        legacy_queue,
    )
    import backend.services.review_service as review_service

    real_replace = review_service.os.replace

    def fail_legacy_replace(source, destination):
        if Path(destination) == legacy_queue:
            raise PermissionError("simulated legacy export lock")
        return real_replace(source, destination)

    monkeypatch.setattr(review_service.os, "replace", fail_legacy_replace)

    result = remove_legacy_active_learning_samples(["deleted-image"])

    assert result.removed_count == 0
    assert not result.complete
    assert runtime_queue.read_text(encoding="utf-8") == '{"image_id":"deleted-image"}\n'
    assert legacy_queue.read_text(encoding="utf-8") == '{"image_id":"deleted-image"}\n'


def test_remove_legacy_samples_does_not_prune_first_file_when_later_file_is_malformed(tmp_path, monkeypatch):
    runtime_queue = tmp_path / "runtime-active-learning.jsonl"
    legacy_queue = tmp_path / "legacy-active-learning.jsonl"
    runtime_bytes = b'{"image_id":"deleted-image"}\n{"image_id":"retained-image"}\n'
    legacy_bytes = b'{"image_id":"deleted-image"}\n{malformed legacy line\n'
    runtime_queue.write_bytes(runtime_bytes)
    legacy_queue.write_bytes(legacy_bytes)
    monkeypatch.setattr(
        "backend.services.review_service.ACTIVE_LEARNING_QUEUE_PATH",
        runtime_queue,
    )
    monkeypatch.setattr(
        "backend.services.review_service._LEGACY_ACTIVE_LEARNING_QUEUE_PATH",
        legacy_queue,
    )

    result = remove_legacy_active_learning_samples(["deleted-image"])

    assert result.removed_count == 0
    assert not result.complete
    assert runtime_queue.read_bytes() == runtime_bytes
    assert legacy_queue.read_bytes() == legacy_bytes


def test_remove_legacy_samples_fails_closed_for_non_file_queue_path(tmp_path, monkeypatch):
    runtime_queue_directory = tmp_path / "runtime-queue-directory"
    runtime_queue_directory.mkdir()
    monkeypatch.setattr(
        "backend.services.review_service.ACTIVE_LEARNING_QUEUE_PATH",
        runtime_queue_directory,
    )
    monkeypatch.setattr(
        "backend.services.review_service._LEGACY_ACTIVE_LEARNING_QUEUE_PATH",
        tmp_path / "missing" / "legacy-active-learning.jsonl",
    )

    result = remove_legacy_active_learning_samples(["deleted-image"])

    assert result.removed_count == 0
    assert not result.complete
