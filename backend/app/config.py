"""
Application configuration, storage directory paths, baseline statistics, and shared service instances.
"""

import hashlib
import json
import os
import re
from pathlib import Path

from backend.core.synthetic_demo import load_synthetic_demo_configuration
from backend.services.model_service import ModelRegistry
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.report_generator import MedicalReportGenerator

# Base Directories
APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))

_env_data_dir = os.environ.get("APP_DATA_DIR")
if _env_data_dir:
    DATA_DIR = os.path.abspath(_env_data_dir) if os.path.isabs(_env_data_dir) else os.path.abspath(os.path.join(PROJECT_ROOT, _env_data_dir))
else:
    DATA_DIR = os.path.join(PROJECT_ROOT, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
SYNTHETIC_DEMO_MODE, SYNTHETIC_DEMO_ALLOWED_UPLOAD_SHA256 = load_synthetic_demo_configuration(
    PROJECT_ROOT,
    DATA_DIR,
)
# The active checkpoint is selected by the manifest below and hash-verified before loading.

_CORE_SCOPE_LOSSES = {
    "0.5bce+0.5dice",
    "0.5dice+0.5bce",
    "0.5bcewithlogits+0.5softdice",
    "0.5softdice+0.5bcewithlogits",
    "bce+dice",
    "dice+bce",
}


def _normalized_loss(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(r"\s+", "", value).casefold()


def _manifest_reference(manifest_path: Path, reference: object) -> Path | None:
    if not isinstance(reference, str) or not reference.strip():
        return None
    declared = Path(reference)
    if declared.is_absolute():
        return declared
    root_candidate = Path(PROJECT_ROOT) / declared
    if root_candidate.is_file():
        return root_candidate
    return manifest_path.parent / declared


def _has_verified_core_loss(manifest_path: Path, selection: dict) -> bool:
    """Require matching training evidence for the project's Dice+BCE core scope."""
    declared_loss = _normalized_loss(selection.get("loss_function"))
    evidence_path = _manifest_reference(manifest_path, selection.get("training_evidence"))
    if declared_loss not in _CORE_SCOPE_LOSSES or evidence_path is None:
        return False
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    evidence_loss = _normalized_loss(evidence.get("loss", evidence.get("loss_function"))) if isinstance(evidence, dict) else None
    return evidence_loss == declared_loss


def selected_checkpoint_path(manifest_path: str | Path) -> str | None:
    """Use only hash-matched checkpoints with verified Dice+BCE training provenance."""
    manifest_path = Path(manifest_path)
    try:
        selection = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(selection, dict) or not _has_verified_core_loss(manifest_path, selection):
            return None
        candidate = _manifest_reference(manifest_path, selection["checkpoint"])
        if candidate is None:
            return None
        digest = hashlib.sha256()
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return str(candidate) if digest.hexdigest() == selection["checkpoint_sha256"] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


_default_selection_path = Path(PROJECT_ROOT) / "evaluation" / "selected_model.json"
SELECTION_MANIFEST_PATH = Path(os.environ.get("MODEL_SELECTION_MANIFEST", _default_selection_path))
if not SELECTION_MANIFEST_PATH.is_absolute():
    SELECTION_MANIFEST_PATH = Path(PROJECT_ROOT) / SELECTION_MANIFEST_PATH
CHECKPOINT_PATH = selected_checkpoint_path(SELECTION_MANIFEST_PATH)
try:
    MODEL_SELECTION = json.loads(SELECTION_MANIFEST_PATH.read_text(encoding="utf-8"))
except (OSError, ValueError):
    MODEL_SELECTION = {}

# Ensure required runtime directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Product identity
SYSTEM_NAME = "Hệ thống Hỗ trợ Phân đoạn Siêu âm Buồng trứng Human-in-the-Loop"
SYSTEM_ENVIRONMENT = os.environ.get("APP_ENVIRONMENT", "LOCAL")
CLINICAL_FACILITY = "Chưa cấu hình cơ sở"
DISCLAIMER = (
    "Hệ thống hỗ trợ phân đoạn đường viền và đo lường kích thước tổn thương buồng trứng (Caliper/Area), "
    "không thay thế chẩn đoán chuyên môn của bác sĩ. Kết quả cần được bác sĩ rà soát và xác nhận."
)

# Shared Service Instances
preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
model_registry = ModelRegistry(checkpoint_path=CHECKPOINT_PATH, model_selection=MODEL_SELECTION)
report_generator = MedicalReportGenerator()

# Feature Flags (v2.0 Architecture)
APP_FEATURES_RAW = os.environ.get(
    "APP_FEATURES",
    "autofill,fast_review,cdss_background,uncertainty_overlay",
)
ENABLED_FEATURES: set[str] = {
    f.strip().lower() for f in APP_FEATURES_RAW.split(",") if f.strip()
}


def is_feature_enabled(name: str) -> bool:
    """Return True if feature flag is active in current configuration."""
    return name.strip().lower() in ENABLED_FEATURES
