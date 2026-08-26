"""
FastAPI Route Handlers package.
"""

from backend.app.routers.admin import router as admin_router
from backend.app.routers.auth import router as auth_router
from backend.app.routers.cases import router as cases_router
from backend.app.routers.health import router as health_router
from backend.app.routers.inference import router as inference_router
from backend.app.routers.reviews import router as reviews_router

__all__ = [
    "admin_router",
    "auth_router",
    "cases_router",
    "health_router",
    "inference_router",
    "reviews_router",
]
