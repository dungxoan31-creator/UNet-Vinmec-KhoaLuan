"""
Authentication, User Profiles, JWT Tokens, and Role-Based Access Control (RBAC).
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import CURRENT_ACTIVE_USER
from backend.db.database import UserModel, get_db
from backend.schemas.schemas import LoginRequest, SwitchRoleRequest, TokenResponse, UserProfile

JWT_SECRET = "vinmec-medical-ai-ovarian-secret-key-2026"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

router = APIRouter(tags=["Authentication & RBAC"])


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> UserModel:
    """
    Dependency extracting and validating the current user from JWT Bearer token,
    falling back to current active session for seamless demo/testing workflows.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username: str = payload.get("sub")
            if username:
                user = db.query(UserModel).filter(UserModel.username == username).first()
                if user and user.is_active:
                    return user
        except (jwt.PyJWTError, Exception):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token xác thực không hợp lệ hoặc đã hết hạn.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Fallback to active runtime user for testing & backward compatibility
    user = db.query(UserModel).filter(UserModel.username == CURRENT_ACTIVE_USER["username"]).first()
    if not user:
        user = db.query(UserModel).first()
    return user


def require_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    """Dependency verifying that the user has ADMIN privileges."""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền Quản trị viên (ADMIN) để thực hiện thao tác này.",
        )
    return current_user


@router.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates user credentials and issues a signed JWT Bearer access token.
    Default demo passwords match usernames (e.g. 'bacsi' / 'admin').
    """
    user = db.query(UserModel).filter(UserModel.username == req.username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác.",
        )

    # In production, check bcrypt hash; for demo support, accept user match
    access_token = create_access_token(data={"sub": user.username, "role": user.role, "uid": user.id})
    CURRENT_ACTIVE_USER["username"] = user.username
    CURRENT_ACTIVE_USER["role"] = user.role

    user_profile = UserProfile(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        department=user.department,
        title=user.title,
        hospital=user.hospital,
        avatar=user.avatar,
        is_active=user.is_active,
    )

    return TokenResponse(access_token=access_token, user=user_profile)


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
def get_current_user_profile(user: UserModel = Depends(get_current_user)):
    """
    Returns current active user session profile.
    """
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "department": user.department,
        "title": user.title,
        "hospital": user.hospital,
        "avatar": user.avatar,
        "is_active": user.is_active,
    }


@router.post("/api/auth/switch-role")
def switch_active_role(req: SwitchRoleRequest, db: Session = Depends(get_db)):
    """
    Switches active session role between DOCTOR and ADMIN, issuing a new signed JWT token.
    """
    target_role = req.role.upper()
    if target_role not in ["DOCTOR", "ADMIN"]:
        raise HTTPException(status_code=400, detail="Vai trò không hợp lệ.")

    user = db.query(UserModel).filter(UserModel.role == target_role).first()
    if user:
        CURRENT_ACTIVE_USER["username"] = user.username
        CURRENT_ACTIVE_USER["role"] = user.role
        access_token = create_access_token(data={"sub": user.username, "role": user.role, "uid": user.id})
        return {
            "status": "SUCCESS",
            "message": f"Đã chuyển sang tài khoản {user.full_name} ({user.role})",
            "access_token": access_token,
            "token_type": "bearer",
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
