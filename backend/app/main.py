"""
FastAPI Application Entry Point for Ovarian Ultrasound AI System.
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import json
import os
import uuid
from datetime import UTC, datetime

from fastapi import Body, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.config import (
    DATA_DIR,
    FRONTEND_DIR,
    REPORTS_DIR,
    UPLOAD_DIR,
    model_registry,
    preprocessor,
    report_generator,
)
from backend.app.routers import (
    admin_router,
    auth_router,
    cases_router,
    evaluation_router,
    health_router,
    hitl_router,
    inference_router,
    reviews_router,
    v1_router,
)
from backend.app.routers.auth import get_current_user
from backend.core.image_utils import cv2_imread_unicode, cv2_imwrite_unicode
from backend.db.database import AuditLogModel, get_db, init_db

# Initialize Database Schema
init_db()

# Initialize FastAPI Application
app = FastAPI(
    title="Ovarian Ultrasound AI Decision Support System",
    description="Backend API for Deep Learning Ultrasound Segmentation & Human-in-the-Loop Clinical Review",
    version="1.2.0",
)

# Enable CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("APP_CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register API Routers
clinical_access = [Depends(get_current_user)]
app.include_router(v1_router, dependencies=clinical_access)
app.include_router(health_router)
app.include_router(cases_router, dependencies=clinical_access)
app.include_router(inference_router, dependencies=clinical_access)
app.include_router(reviews_router, dependencies=clinical_access)
app.include_router(hitl_router, dependencies=clinical_access)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(evaluation_router, prefix="/api/evaluation", tags=["Evaluation"], dependencies=clinical_access)

# Mount Static Assets and Data Directories
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", tags=["Web UI"])
def serve_ui():
    """
    Serves the primary clinical frontend web application.
    """
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Ovarian Ultrasound AI Backend Running.</h1>")


@app.get("/admin", tags=["Web UI"])
def serve_admin_ui():
    """
    Direct route for Admin Governance Portal.
    """
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Vinmec AI Admin Portal Running.</h1>")


@app.get("/api/notifications")
def get_notifications():
    """Return clinical workstation notifications."""
    return []


@app.post("/api/notifications/read")
def read_notifications(payload: dict = Body(default={})):
    """Mark workstation notifications as read."""
    return {"status": "SUCCESS"}


@app.post("/api/feedback")
def submit_feedback(payload: dict = Body(default={}), db: Session = Depends(get_db)):
    """Acknowledge doctor feedback and suggestions with durable audit logging."""
    audit_entry = AuditLogModel(
        entity_name="user_feedback",
        entity_id=str(uuid.uuid4()),
        action_type="USER_FEEDBACK",
        actor_id=payload.get("actor_id") or payload.get("username") or "doctor",
        details=payload if payload else {},
        timestamp=datetime.now(UTC),
    )
    db.add(audit_entry)
    db.commit()
    return {"status": "SUCCESS", "message": "Đã ghi nhận góp ý của bác sĩ.", "feedback_id": str(audit_entry.id)}


# Backward compatibility re-exports
__all__ = [
    "DATA_DIR",
    "FRONTEND_DIR",
    "REPORTS_DIR",
    "UPLOAD_DIR",
    "app",
    "cv2_imread_unicode",
    "cv2_imwrite_unicode",
    "model_registry",
    "preprocessor",
    "report_generator",
]
