import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import AuditLogModel, UserModel, get_db
from backend.schemas.schemas import LoginRequest, RegisterRequest, TokenResponse, UserProfile

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
router = APIRouter(tags=["Authentication & RBAC"])


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}:{key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        if not hashed or ":" not in hashed:
            return False
        salt, key_hex = hashed.split(":", 1)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return secrets.compare_digest(key, expected_key)
    except Exception:
        return False


def _signing_key() -> str:
    key = os.environ.get("APP_JWT_SECRET", "")
    if len(key) < 32:
        raise HTTPException(status_code=503, detail="Configure APP_JWT_SECRET with at least 32 characters.")
    return key


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "purpose": "access",
        "type": "access",
        **data,
        "exp": now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)),
        "iat": now,
    }
    return jwt.encode(payload, _signing_key(), algorithm=JWT_ALGORITHM)


def get_current_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> UserModel:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(authorization[7:], _signing_key(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc

    # Enforce token purpose separation: reject tokens intended for reset_password or not marked for access
    if payload.get("purpose") == "reset_password" or payload.get("type") == "reset":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    username = payload.get("sub")
    uid = payload.get("uid")
    token_ver = payload.get("token_version")
    iat = payload.get("iat")

    user = db.query(UserModel).filter(UserModel.username == username).first() if username else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account unavailable.")

    # BE-07: Ensure token belongs to this user ID if uid is present, or was not issued prior to account creation
    if uid and user.id != uid:
        raise HTTPException(status_code=401, detail="Account identity changed.")
    created_at = getattr(user, "created_at", None)
    if not uid and created_at is not None and iat is not None:
        created_ts = (created_at.replace(tzinfo=UTC) if created_at.tzinfo is None else created_at).timestamp()
        if float(iat) < (created_ts - 1.0):
            raise HTTPException(status_code=401, detail="Account identity changed.")

    # BE-06: Check token revocation on password change / reset / logout
    if token_ver is not None and getattr(user, "token_version", None) is not None:
        if token_ver != user.token_version:
            raise HTTPException(status_code=401, detail="Token has been revoked.")
    else:
        revoked_at = getattr(user, "tokens_revoked_at", None)
        if revoked_at is not None and iat is not None:
            revoked_ts = (revoked_at.replace(tzinfo=UTC) if revoked_at.tzinfo is None else revoked_at).timestamp()
            if float(iat) <= revoked_ts:
                raise HTTPException(status_code=401, detail="Token has been revoked.")

    return user


def require_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin role required.")
    return current_user


def require_clinical(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.role != "DOCTOR":
        raise HTTPException(
            status_code=403,
            detail="Tài khoản quản trị viên hoặc phi lâm sàng không có quyền truy cập hồ sơ và hình ảnh người bệnh.",
        )
    return current_user


@router.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    username = req.username.strip().lower()
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if not user or not user.is_active:
        db.add(
            AuditLogModel(
                entity_name="auth",
                entity_id=username or "anonymous",
                action_type="LOGIN_FAILURE",
                actor_id=username or "anonymous",
                details={"reason": "user_not_found_or_inactive"},
                timestamp=datetime.now(UTC),
            )
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    password = req.password or ""
    pwd_valid = False
    if user.password_hash:
        pwd_valid = verify_password(password, user.password_hash)
    else:
        password_variable = "APP_ADMIN_PASSWORD" if user.role == "ADMIN" else "APP_DOCTOR_PASSWORD"
        configured_password = os.environ.get(password_variable)
        pwd_valid = bool(configured_password and secrets.compare_digest(password, configured_password))

    if not pwd_valid:
        db.add(
            AuditLogModel(
                entity_name="auth",
                entity_id=user.id,
                action_type="LOGIN_FAILURE",
                actor_id=user.username,
                details={"reason": "invalid_credentials"},
                timestamp=datetime.now(UTC),
            )
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    db.add(
        AuditLogModel(
            entity_name="auth",
            entity_id=user.id,
            action_type="LOGIN_SUCCESS",
            actor_id=user.username,
            details={"role": user.role},
            timestamp=datetime.now(UTC),
        )
    )
    db.commit()

    return TokenResponse(
        access_token=create_access_token({
            "sub": user.username,
            "uid": user.id,
            "token_version": getattr(user, "token_version", 1) or 1,
        }),
        user=UserProfile.model_validate(user, from_attributes=True),
    )


@router.post("/api/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if req.role and req.role.upper() == "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Không thể tự cấp quyền quản trị viên qua đăng ký công khai.",
        )

    username = req.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Tên đăng nhập phải có ít nhất 3 ký tự.")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 6 ký tự.")
    if not req.full_name or len(req.full_name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Họ và tên không được để trống.")

    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại trong hệ thống.")

    new_user = UserModel(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip(),
        role="DOCTOR",
        department=req.department or "Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa",
        title=req.title or "BS",
        hospital=req.hospital or "Bệnh viện ĐKQT Vinmec Times City",
        avatar="doctor_avatar.png",
        is_active=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return TokenResponse(
        access_token="",
        user=UserProfile.model_validate(new_user, from_attributes=True),
    )


@router.get("/api/auth/users", response_model=list[UserProfile], dependencies=[Depends(require_admin)])
def get_system_users(db: Session = Depends(get_db)):
    return [UserProfile.model_validate(user, from_attributes=True) for user in db.query(UserModel).all()]


@router.get("/api/auth/current-user", response_model=UserProfile)
def get_current_user_profile(user: UserModel = Depends(get_current_user)):
    return UserProfile.model_validate(user, from_attributes=True)


def create_reset_token(username: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "purpose": "reset_password",
        "jti": str(uuid.uuid4()),
        "exp": now + (expires_delta or timedelta(hours=1)),
        "iat": now,
    }
    return jwt.encode(payload, _signing_key(), algorithm=JWT_ALGORITHM)


@router.post("/api/auth/forgot-password")
def forgot_password(payload: dict = Body(default={}), db: Session = Depends(get_db)):
    """Accept password recovery request."""
    username = (payload.get("username") or "").strip().lower()
    user = db.query(UserModel).filter(UserModel.username == username).first() if username else None
    if user:
        # Secure out-of-band delivery: token must never be leaked in public HTTP response
        create_reset_token(user.username)
    return {
        "status": "SUCCESS",
        "message": "Nếu tài khoản tồn tại, yêu cầu đặt lại mật khẩu đã được tiếp nhận.",
    }


@router.post("/api/auth/reset-password")
def reset_password(payload: dict = Body(default={}), db: Session = Depends(get_db)):
    """Reset account password via secure token."""
    username = (payload.get("username") or "").strip().lower()
    token = (payload.get("token") or "").strip()
    new_pw = payload.get("new_password", "")

    if not token:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu không được để trống.")
    if not new_pw or len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 6 ký tự.")

    try:
        data = jwt.decode(token, _signing_key(), algorithms=[JWT_ALGORITHM])
        if data.get("purpose") != "reset_password":
            raise HTTPException(status_code=400, detail="Token không hợp lệ.")
        token_user = (data.get("sub") or "").lower()
        if username and token_user != username:
            raise HTTPException(status_code=400, detail="Token không khớp với người dùng.")
        target_username = token_user or username
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.") from exc

    token_id = str(data.get("jti") or hashlib.sha256(token.encode("utf-8")).hexdigest()[:36])
    already_used = (
        db.query(AuditLogModel)
        .filter(
            AuditLogModel.entity_name == "consumed_reset_token",
            AuditLogModel.entity_id == token_id,
        )
        .first()
    )
    if already_used:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu đã được sử dụng.")

    user = db.query(UserModel).filter(UserModel.username == target_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng.")

    user.password_hash = hash_password(new_pw)
    user.tokens_revoked_at = datetime.now(UTC)
    user.token_version = (getattr(user, "token_version", 1) or 1) + 1
    db.add(
        AuditLogModel(
            entity_name="consumed_reset_token",
            entity_id=token_id,
            action_type="TOKEN_CONSUMED",
            actor_id=target_username,
            details={"consumed_at": datetime.now(UTC).isoformat()},
        )
    )
    db.commit()
    return {"status": "SUCCESS", "message": "Mật khẩu đã được đặt lại thành công."}


@router.post("/api/auth/change-password")
def change_password(payload: dict = Body(default={}), user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Allow logged in user to update clinical credentials."""
    old_pw = payload.get("old_password") or payload.get("current_password") or ""
    new_pw = payload.get("new_password", "")
    if not new_pw:
        raise HTTPException(status_code=400, detail="Mật khẩu mới không được để trống")
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 6 ký tự")

    if user.password_hash:
        if not verify_password(old_pw, user.password_hash):
            raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
    else:
        password_variable = "APP_ADMIN_PASSWORD" if user.role == "ADMIN" else "APP_DOCTOR_PASSWORD"
        configured_password = os.environ.get(password_variable)
        if not configured_password or not secrets.compare_digest(old_pw, configured_password):
            raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")

    user.password_hash = hash_password(new_pw)
    user.tokens_revoked_at = datetime.now(UTC)
    user.token_version = (getattr(user, "token_version", 1) or 1) + 1
    db.commit()
    return {"status": "SUCCESS", "message": "Đổi mật khẩu thành công."}


@router.post("/api/auth/logout")
def logout(user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Invalidate current user session and revoke active tokens."""
    user.tokens_revoked_at = datetime.now(UTC)
    user.token_version = (getattr(user, "token_version", 1) or 1) + 1
    db.commit()
    return {"status": "SUCCESS", "message": "Đã đăng xuất và thu hồi phiên làm việc."}


@router.post("/api/auth/refresh")
def refresh_token(user: UserModel = Depends(get_current_user)):
    """Renew clinical session JWT token."""
    token = create_access_token({
        "sub": user.username,
        "uid": user.id,
        "token_version": getattr(user, "token_version", 1) or 1,
    })
    return {"access_token": token, "token_type": "bearer", "expires_in": 86400}
