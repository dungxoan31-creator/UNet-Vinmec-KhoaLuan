"""Shared authentication dependencies and token/password primitives for the API."""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import UserModel, get_db

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


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
        payload = jwt.decode(
            authorization[7:],
            _signing_key(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc

    if payload.get("purpose") == "reset_password" or payload.get("type") == "reset":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    username = payload.get("sub")
    uid = payload.get("uid")
    token_ver = payload.get("token_version")
    issued_at = payload.get("iat")

    user = db.query(UserModel).filter(UserModel.username == username).first() if username else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account unavailable.")
    if user.email and not user.email_verified:
        raise HTTPException(status_code=401, detail="Account unavailable.")

    if uid and user.id != uid:
        raise HTTPException(status_code=401, detail="Account identity changed.")
    created_at = getattr(user, "created_at", None)
    if not uid and created_at is not None and issued_at is not None:
        created_ts = (created_at.replace(tzinfo=UTC) if created_at.tzinfo is None else created_at).timestamp()
        if float(issued_at) < (created_ts - 1.0):
            raise HTTPException(status_code=401, detail="Account identity changed.")

    if token_ver is not None and getattr(user, "token_version", None) is not None:
        if token_ver != user.token_version:
            raise HTTPException(status_code=401, detail="Token has been revoked.")
    else:
        revoked_at = getattr(user, "tokens_revoked_at", None)
        if revoked_at is not None and issued_at is not None:
            revoked_ts = (revoked_at.replace(tzinfo=UTC) if revoked_at.tzinfo is None else revoked_at).timestamp()
            if float(issued_at) <= revoked_ts:
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
