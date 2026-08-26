"""
Application configuration, storage directory paths, baseline statistics, and shared service instances.
"""

import os

from backend.services.model_service import ModelRegistry
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.report_generator import MedicalReportGenerator

# Base Directories
APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "checkpoints", "best_attention_unet.pth")

# Ensure required runtime directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Active session memory
CURRENT_ACTIVE_USER = {"username": "bacsi", "role": "DOCTOR"}

# Baseline Statistics
BASELINE_RECEIVED = 435
BASELINE_APPROVED = 311
BASELINE_PENDING = 124  # 435 - 311
BASELINE_ACCEPTED_RAW = 256.575  # 256.575 / 311 = exactly 82.5%

# Shared Service Instances
preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
model_registry = ModelRegistry(checkpoint_path=CHECKPOINT_PATH if os.path.exists(CHECKPOINT_PATH) else None)
report_generator = MedicalReportGenerator()
