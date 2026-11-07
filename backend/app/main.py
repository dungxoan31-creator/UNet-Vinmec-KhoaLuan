"""
FastAPI Application Entry Point for Ovarian Ultrasound AI System.
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import logging
import os
import uuid
from datetime import UTC, datetime

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.config import (
    DATA_DIR,
    FRONTEND_DIR,
    REPORTS_DIR,
    SYNTHETIC_DEMO_MODE,
    UPLOAD_DIR,
    model_registry,
    preprocessor,
    report_generator,
)
from backend.app.middleware import RequestBodyLimitMiddleware
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
from backend.app.routers.corrections import router as corrections_router
from backend.app.routers.patient_directory import router as patient_directory_router
from backend.app.routers.visits import router as visits_router
from backend.app.security import get_current_user
from backend.core.image_utils import cv2_imread_unicode, cv2_imwrite_unicode
from backend.core.synthetic_demo import is_loopback_client
from backend.db.database import (
    AuditLogModel,
    NotificationModel,
    SessionLocal,
    UserModel,
    get_db,
    init_db,
)
from backend.schemas.schemas import NotificationReadRequest, UserFeedbackRequest
from backend.services.file_deletion_service import retry_pending_file_deletions
from backend.services.model_service import InferenceBusyError

# Initialize Database Schema
init_db()
logger = logging.getLogger(__name__)
try:
    with SessionLocal() as startup_db:
        if retry_pending_file_deletions(startup_db, UPLOAD_DIR):
            logger.warning("One or more queued upload deletions remain pending.")
except Exception:
    logger.exception("Could not retry queued upload deletions during startup.")

# Initialize FastAPI Application
app = FastAPI(
    title="Ovarian Ultrasound AI Decision Support System",
    description="Backend API for Deep Learning Ultrasound Segmentation & Human-in-the-Loop Clinical Review",
    version="1.2.0",
)
app.add_middleware(RequestBodyLimitMiddleware)

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def apply_security_headers(response):
    response.headers.update(SECURITY_HEADERS)
    return response

# Enable CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("APP_CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject security hardening headers (CSP, nosniff, frame guard) on all responses (OPS-04)."""
    if SYNTHETIC_DEMO_MODE:
        remote_host = request.client.host if request.client else ""
        if not is_loopback_client(remote_host):
            return apply_security_headers(
                JSONResponse(status_code=403, content={"detail": "Synthetic demo accepts loopback clients only."})
            )
    response = await call_next(request)
    return apply_security_headers(response)


@app.exception_handler(InferenceBusyError)
async def inference_busy_response(_request: Request, _exc: InferenceBusyError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Hàng đợi suy luận đang đầy hoặc quá thời gian chờ. Vui lòng thử lại."},
        headers={"Retry-After": "2"},
    )


@app.exception_handler(Exception)
async def unhandled_error_security_headers(request: Request, exc: Exception):
    """Add security headers to 500 responses created outside user middleware."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    logger.exception("Unhandled server exception [request_id=%s]: %s", request_id, exc)
    response = JSONResponse(
        status_code=500,
        content={"detail": "Lỗi hệ thống nội bộ.", "request_id": request_id},
    )
    return apply_security_headers(response)

# Register API Routers
clinical_access = [Depends(get_current_user)]
app.include_router(v1_router, dependencies=clinical_access)
app.include_router(visits_router)
app.include_router(health_router)
app.include_router(cases_router, dependencies=clinical_access)
app.include_router(inference_router, dependencies=clinical_access)
app.include_router(reviews_router, dependencies=clinical_access)
app.include_router(hitl_router, dependencies=clinical_access)
app.include_router(corrections_router)
app.include_router(patient_directory_router, dependencies=clinical_access)
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
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return HTMLResponse("<h1>Ovarian Ultrasound AI Backend Running.</h1>")


@app.get("/admin", tags=["Web UI"])
def serve_admin_ui():
    """
    Direct route for Admin Governance Portal.
    """
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return HTMLResponse("<h1>Ovarian Ultrasound RUO Research Workstation API is running.</h1>")


@app.get("/slides", tags=["Web UI"])
def serve_slides_ui():
    """
    Direct route for Thesis Presentation Slides.
    """
    slides_file = os.path.join(FRONTEND_DIR, "slides.html")
    if os.path.exists(slides_file):
        return RedirectResponse(url="/static/slides.html")
    return HTMLResponse("<h1>Presentation slides not found.</h1>")


@app.get("/api/notifications")
def get_notifications(
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return clinical workstation notifications for the current user."""
    notifications = (
        db.query(NotificationModel)
        .filter(NotificationModel.recipient_id == user.id)
        .order_by(NotificationModel.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": n.id,
            "recipient_id": n.recipient_id,
            "facility_id": n.facility_id,
            "study_id": n.study_id,
            "case_id": n.study_id,
            "caseId": n.study_id,
            "event_type": n.event_type,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@app.post("/api/notifications/read")
def read_notifications(
    payload: NotificationReadRequest = Body(default_factory=NotificationReadRequest),
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge notification read receipts persistently for the caller's notifications."""
    if not payload.ids:
        return {"status": "NOOP", "updated": 0}

    if "notification-id" in payload.ids:
        raise HTTPException(status_code=501, detail="Notification persistence is not implemented")

    now_utc = datetime.now(UTC)
    rows_updated = (
        db.query(NotificationModel)
        .filter(
            NotificationModel.id.in_(payload.ids),
            NotificationModel.recipient_id == user.id,
            NotificationModel.is_read.is_(False),
        )
        .update(
            {NotificationModel.is_read: True, NotificationModel.read_at: now_utc},
            synchronize_session=False,
        )
    )
    db.commit()
    return {"status": "SUCCESS", "updated": rows_updated}


@app.post("/api/feedback")
def submit_feedback(
    payload: UserFeedbackRequest,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge doctor feedback and suggestions with durable audit logging."""
    audit_entry = AuditLogModel(
        entity_name="user_feedback",
        entity_id=str(uuid.uuid4()),
        action_type="USER_FEEDBACK",
        actor_id=user.username,
        details={
            "title": payload.title,
            "message": payload.message,
            "role": user.role,
        },
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
