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
# Model Checkpoints (Standard U-Net Baseline & Attention U-Net Comparative Variant)
BASELINE_CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "checkpoints", "baseline_unet_best.pth")
ATTENTION_CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "checkpoints", "best_attention_unet.pth")
CHECKPOINT_PATH = BASELINE_CHECKPOINT_PATH if os.path.exists(BASELINE_CHECKPOINT_PATH) else ATTENTION_CHECKPOINT_PATH

# Ensure required runtime directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Active session memory
CURRENT_ACTIVE_USER = {"username": "bacsi", "role": "DOCTOR"}

# System Environment & Thesis Positioning
SYSTEM_NAME = "Hệ thống Thử nghiệm Hỗ trợ Phân đoạn Siêu âm Buồng trứng Human-in-the-Loop"
SYSTEM_ENVIRONMENT = "EXPERIMENTAL_RESEARCH_PROTOTYPE"
CLINICAL_FACILITY = "Bệnh viện Đa khoa Quốc tế Vinmec Times City"
DISCLAIMER = (
    "Hệ thống là bản mẫu nghiên cứu thực nghiệm trong khuôn khổ Khóa luận Tốt nghiệp (MIS / ITBA - NEU). "
    "Hệ thống hỗ trợ phân đoạn đường viền và đo lường kích thước tổn thương buồng trứng (Caliper/Area), "
    "không thay thế chẩn đoán chuyên môn của bác sĩ và không phải phần mềm thương mại triển khai chính thức của Vinmec."
)

# Vinmec Times City Thesis Dataset Statistics (1,387 total images, 417 with initial masks)
TOTAL_COLLECTED_IMAGES = 1387
TOTAL_UNANNOTATED_IMAGES = 970
BASELINE_RECEIVED = 417       # Total images with initial masks
BASELINE_APPROVED = 307       # Officially verified Ground Truth images (from 185 unique patients)
BASELINE_PENDING = 110        # Pending expert doctor review (417 - 307)
BASELINE_ACCEPTED_RAW = 253   # ~82.4% direct acceptance rate

# Shared Service Instances
preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
model_registry = ModelRegistry(checkpoint_path=CHECKPOINT_PATH if os.path.exists(CHECKPOINT_PATH) else None)
report_generator = MedicalReportGenerator()
