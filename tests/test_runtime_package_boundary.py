"""Verify runtime modules without the training or scripts folders Docker excludes."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_training_and_serving_share_the_same_label_order():
    from ai_training.mmotu_label_schema import MMOTU_8_CLASSES as training
    from backend.core.mmotu_labels import MMOTU_8_CLASSES as serving

    assert training is serving
    assert len(serving) == 8


def test_postgres_compose_driver_is_declared_and_loadable_without_connecting():
    from sqlalchemy import create_engine

    assert "psycopg[binary]>=3.3.6" in (ROOT / "requirements.txt").read_text()
    lock = (ROOT / "requirements-lock.txt").read_text()
    assert "psycopg==3.3.6" in lock and "psycopg-binary==3.3.6" in lock
    engine = create_engine("postgresql+psycopg://synthetic:synthetic@127.0.0.1:1/unused")
    try:
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()


def test_app_imports_and_enhancement_executes_without_training_or_scripts(tmp_path):
    package = tmp_path / "package"
    shutil.copytree(ROOT / "backend", package / "backend", ignore=shutil.ignore_patterns("__pycache__"))
    (package / "frontend").mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    env = {**os.environ, "APP_DATA_DIR": str(runtime), "APP_DB_PATH": str(runtime / "test.sqlite3"),
           "DATABASE_URL": "", "MODEL_SELECTION_MANIFEST": str(runtime / "absent-selection.json"),
           "APP_SYNTHETIC_DEMO_MODE": "false", "APP_SYNTHETIC_DEMO_FIXTURE_DIR": "",
           "APP_ENVIRONMENT": "TEST", "APP_JWT_SECRET": "synthetic-package-jwt-secret-at-least-32-characters",
           "APP_PATIENT_PID_HMAC_SECRET": "synthetic-package-hmac-secret-at-least-32-characters",
           "APP_DOCTOR_PASSWORD": "synthetic-package-doctor-2026", "APP_ADMIN_PASSWORD": "synthetic-package-admin-2026"}
    code = """
import sys
sys.path.insert(0, sys.argv[1])
from backend.app.main import app
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.image_classifier import ResearchImageClassifier
import numpy as np
pixels = np.random.default_rng(42).integers(30, 180, (128, 256), dtype=np.uint8)
tensor, padded, transform, quality = UltrasoundPreprocessor().preprocess_for_inference(pixels, denoise_method='lee')
assert padded.shape == (512, 512)
assert tensor.shape == (1, 1, 512, 512)
assert ResearchImageClassifier().predict(pixels)['status'] == 'UNAVAILABLE'
assert '/api/images/{image_id}/classify' in app.openapi()['paths']
assert not any(name == 'ai_training' or name.startswith('ai_training.') or name == 'scripts' or name.startswith('scripts.') for name in sys.modules)
print('PASS: runtime-only package imports, Lee filter executes, absent weights fail closed')
"""
    result = subprocess.run([sys.executable, "-I", "-c", code, str(package)], cwd=package, env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: runtime-only package" in result.stdout
