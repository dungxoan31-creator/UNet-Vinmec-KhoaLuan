"""
Authentication, User Profiles, and Role Switching endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.config import CURRENT_ACTIVE_USER
from backend.db.database import UserModel, get_db
from backend.schemas.schemas import SwitchRoleRequest, UserProfile

router = APIRouter(tags=["Authentication & RBAC"])


@router.get("/api/auth/users", response_model=list[UserProfile])
def get_system_users(db: Session = Depends(get_db)):
    """
    Returns available user accounts (Doctor vs Admin).
    """
    users = db.query(UserModel).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "department": u.department,
            "title": u.title,
            "hospital": u.hospital,
            "avatar": u.avatar,
            "is_active": u.is_active,
        }
        for u in users
    ]


@router.get("/api/auth/current-user", response_model=UserProfile)
def get_current_user_profile(db: Session = Depends(get_db)):
    """
    Returns current active user session profile.
    """
    user = db.query(UserModel).filter(UserModel.username == CURRENT_ACTIVE_USER["username"]).first()
    if not user:
        user = db.query(UserModel).first()

    return {
        "id": user.id if user else "1",
        "username": user.username if user else "bacsi",
        "full_name": user.full_name if user else "BS.CKI Nguyễn Văn A",
        "role": user.role if user else "DOCTOR",
        "department": user.department if user else "Khoa Chẩn đoán Hình ảnh & Phụ sản",
        "title": user.title if user else "Bác Sĩ Khám & Ký Duyệt",
        "hospital": user.hospital if user else "Vinmec Times City",
        "avatar": user.avatar if user else "doctor_a",
        "is_active": True,
    }


@router.post("/api/auth/switch-role")
def switch_active_role(req: SwitchRoleRequest, db: Session = Depends(get_db)):
    """
    Switches active session role between DOCTOR and ADMIN.
    """
    target_role = req.role.upper()
    if target_role not in ["DOCTOR", "ADMIN"]:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ.")

    user = db.query(UserModel).filter(UserModel.role == target_role).first()
    if user:
        CURRENT_ACTIVE_USER["username"] = user.username
        CURRENT_ACTIVE_USER["role"] = user.role
        return {
            "status": "SUCCESS",
            "message": f"Đã chuyển sang tài khoản {user.full_name} ({user.role})",
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "department": user.department,
                "title": user.title,
                "hospital": user.hospital,
            },
        }

    CURRENT_ACTIVE_USER["role"] = target_role
    return {"status": "SUCCESS", "role": target_role}
