import hashlib
import hmac
import logging
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import case, func, or_, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.app.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    _signing_key,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    require_clinical,
    verify_password,
)
from backend.db.database import (
    AuditLogModel,
    AuthRateLimitModel,
    ConsumedPasswordResetTokenModel,
    EmailVerificationChallengeModel,
    UserModel,
    get_db,
)
from backend.schemas.schemas import (
    ChangePasswordRequest,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegistrationResponse,
    ResendEmailVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserProfile,
)
from backend.services.email_service import (
    EmailDeliveryError,
    ensure_password_reset_delivery_configured,
    send_password_reset_email,
    send_registration_otp,
)

router = APIRouter(tags=["Authentication & RBAC"])
logger = logging.getLogger(__name__)

__all__ = [
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "JWT_ALGORITHM",
    "create_access_token",
    "get_current_user",
    "hash_password",
    "require_admin",
    "require_clinical",
    "router",
    "verify_password",
]

_MAX_AUTH_ATTEMPTS = 5
_MAX_PUBLIC_AUTH_ATTEMPTS = 30
_AUTH_WINDOW_SECONDS = 60.0
_EMAIL_CODE_TTL = timedelta(minutes=10)
_EMAIL_CODE_MAX_ATTEMPTS = 5
_EMAIL_CODE_MAX_RESENDS = 3
_EMAIL_CODE_RESEND_DELAY = timedelta(seconds=60)


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _email_code_digest(email: str, code: str) -> str:
    message = f"{email}:{code}".encode()
    return hmac.new(_signing_key().encode("utf-8"), message, hashlib.sha256).hexdigest()


def _rollback_auth_safely(db: Session, operation: str) -> None:
    try:
        db.rollback()
    except Exception as rollback_error:
        logger.critical(
            "Authentication transaction rollback failed.",
            extra={
                "auth_rollback_failure": True,
                "auth_operation": operation,
                "rollback_error_type": type(rollback_error).__name__,
            },
        )
        try:
            db.close()
        except Exception as close_error:
            logger.critical(
                "Authentication session close failed after rollback error.",
                extra={
                    "auth_session_close_failure": True,
                    "auth_operation": operation,
                    "close_error_type": type(close_error).__name__,
                },
            )


def _verify_pending_registration(bind, user_id: str, challenge_id: str, email: str, code_digest: str):
    if bind is None:
        return None
    try:
        with Session(bind=bind) as verify_db:
            user = verify_db.get(UserModel, user_id)
            challenge = verify_db.get(EmailVerificationChallengeModel, challenge_id)
            if user is None and challenge is None:
                return False
            if user is None or challenge is None:
                return None
            if (
                user.email != email
                or user.email_verified
                or user.is_active
                or challenge.email != email
                or challenge.code_digest != code_digest
                or challenge.expires_at <= _utc_now_naive()
            ):
                return None
            return True
    except Exception:
        return None


def _discard_pending_registration(bind, user_id: str, challenge_id: str, email: str) -> None:
    if bind is None:
        raise RuntimeError("Registration cleanup database bind unavailable")
    cleanup_db = Session(bind=bind)
    try:
        user = cleanup_db.get(UserModel, user_id)
        challenge = cleanup_db.get(EmailVerificationChallengeModel, challenge_id)
        if user and (user.email != email or user.email_verified or user.is_active):
            raise RuntimeError("Registration is no longer pending")
        if challenge and challenge.email != email:
            raise RuntimeError("Registration challenge does not match pending account")
        if challenge:
            cleanup_db.delete(challenge)
        if user:
            cleanup_db.delete(user)
        if challenge or user:
            cleanup_db.commit()
    except Exception:
        _rollback_auth_safely(cleanup_db, "registration_email_compensation")
        raise
    finally:
        cleanup_db.close()


def _verify_password_reset_commit(bind, token_id: str, username: str, token_version: int, new_password: str):
    if bind is None:
        return None
    try:
        with Session(bind=bind) as verify_db:
            user = verify_db.query(UserModel).filter_by(username=username).first()
            consumed = verify_db.get(ConsumedPasswordResetTokenModel, token_id)
            if user is None:
                return None
            if consumed is None:
                return False if (getattr(user, "token_version", 1) or 1) == token_version else None
            audit_exists = (
                verify_db.query(AuditLogModel.id)
                .filter_by(
                    entity_name="consumed_reset_token",
                    entity_id=token_id,
                    action_type="TOKEN_CONSUMED",
                    actor_id=username,
                )
                .first()
                is not None
            )
            if (
                consumed.username != username
                or (getattr(user, "token_version", 1) or 1) != token_version + 1
                or user.must_change_password
                or user.tokens_revoked_at is None
                or not verify_password(new_password, user.password_hash or "")
                or not audit_exists
            ):
                return None
            return True
    except Exception:
        return None


def _verify_resend_challenge_commit(
    bind,
    challenge_id: str,
    email: str,
    code_digest: str,
    resend_count: int,
    sent_at: datetime,
    expires_at: datetime,
):
    if bind is None:
        return None
    try:
        with Session(bind=bind) as verify_db:
            challenge = verify_db.get(EmailVerificationChallengeModel, challenge_id)
            if challenge is None:
                return False
            if (
                challenge.email != email
                or challenge.code_digest != code_digest
                or challenge.resend_count != resend_count
                or challenge.last_sent_at != sent_at
                or challenge.expires_at != expires_at
            ):
                return False
            return True
    except Exception:
        return None


def _verify_email_confirmation_commit(bind, user_id: str, challenge_id: str):
    if bind is None:
        return None
    try:
        with Session(bind=bind) as verify_db:
            user = verify_db.get(UserModel, user_id)
            challenge = verify_db.get(EmailVerificationChallengeModel, challenge_id)
            audit_exists = (
                verify_db.query(AuditLogModel.id)
                .filter_by(entity_name="auth", entity_id=user_id, action_type="EMAIL_VERIFIED")
                .first()
                is not None
            )
            if user is None:
                return None
            if user.email_verified and challenge is None and audit_exists:
                return {"activation_pending": not user.is_active}
            if not user.email_verified and challenge is not None and not audit_exists:
                return False
            return None
    except Exception:
        return None


def _new_email_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _reserve_auth_attempt(
    username: str,
    db: Session,
    *,
    namespace: str | None = None,
    max_attempts: int = _MAX_AUTH_ATTEMPTS,
) -> str:
    secret = _signing_key().encode("utf-8")
    if namespace is not None:
        secret = hmac.new(secret, f"auth-rate-limit:{namespace}".encode(), hashlib.sha256).digest()
    subject_key = hmac.new(secret, username.encode("utf-8"), hashlib.sha256).hexdigest()
    now = _utc_now_naive()
    expired_before = now - timedelta(seconds=_AUTH_WINDOW_SECONDS)
    record = db.get(AuthRateLimitModel, subject_key)
    if (
        record is not None
        and record.window_started_at > expired_before
        and record.attempt_count >= max_attempts
    ):
        raise HTTPException(
            status_code=429,
            detail="Quá nhiều yêu cầu. Vui lòng thử lại sau.",
        )

    statement = sqlite_insert(AuthRateLimitModel).values(
        subject_key=subject_key,
        window_started_at=now,
        attempt_count=1,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[AuthRateLimitModel.subject_key],
        set_={
            "window_started_at": case(
                (AuthRateLimitModel.window_started_at <= expired_before, now),
                else_=AuthRateLimitModel.window_started_at,
            ),
            "attempt_count": case(
                (AuthRateLimitModel.window_started_at <= expired_before, 1),
                else_=AuthRateLimitModel.attempt_count + 1,
            ),
        },
        where=or_(
            AuthRateLimitModel.window_started_at <= expired_before,
            AuthRateLimitModel.attempt_count < max_attempts,
        ),
    )
    db.query(AuthRateLimitModel).filter(
        AuthRateLimitModel.window_started_at <= expired_before
    ).delete(synchronize_session=False)
    result = db.execute(statement)
    if result.rowcount == 0:
        raise HTTPException(
            status_code=429,
            detail="Quá nhiều yêu cầu. Vui lòng thử lại sau.",
        )
    db.commit()

    record = db.get(AuthRateLimitModel, subject_key)
    if record is None:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable.")
    return subject_key


def _reserve_public_auth_attempt(request: Request, db: Session) -> None:
    """Throttle public auth routes by the socket peer, never by forwarded headers."""
    if os.getenv("APP_AUTH_IP_RATE_LIMIT_ENABLED", "true").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return
    if request.client is None or not request.client.host:
        raise HTTPException(status_code=503, detail="Authentication source is unavailable.")
    try:
        with Session(bind=db.get_bind()) as limiter_db:
            _reserve_auth_attempt(
                request.client.host,
                limiter_db,
                namespace="public-auth-ip",
                max_attempts=_MAX_PUBLIC_AUTH_ATTEMPTS,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Public authentication rate limiter is unavailable.",
            extra={"public_auth_rate_limit_storage_error": type(exc).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail="Authentication is temporarily unavailable.",
        ) from exc




@router.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _reserve_public_auth_attempt(request, db)
    username = req.username.strip().lower()
    auth_subject_key = _reserve_auth_attempt(username, db)

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

    db.query(AuthRateLimitModel).filter_by(subject_key=auth_subject_key).delete(
        synchronize_session=False
    )
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
        must_change_password=bool(getattr(user, "must_change_password", False)),
    )


@router.post(
    "/api/auth/register",
    response_model=RegistrationResponse,
    status_code=202,
)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    _reserve_public_auth_attempt(request, db)
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
    existing_email = (
        db.query(UserModel)
        .filter(func.lower(UserModel.email) == req.email)
        .first()
    )
    if existing or existing_email:
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại trong hệ thống.")

    new_user = UserModel(
        id=str(uuid.uuid4()),
        username=username,
        email=req.email,
        email_verified=False,
        password_hash=hash_password(req.password),
        full_name=req.full_name.strip(),
        role="DOCTOR",
        department=req.department or "Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa",
        title=req.title or "BS",
        hospital=req.hospital or "Chưa cấu hình",
        avatar="doctor_avatar.png",
        is_active=False,
    )
    code = _new_email_code()
    now = _utc_now_naive()
    challenge_id = str(uuid.uuid4())
    code_digest = _email_code_digest(req.email, code)
    challenge = EmailVerificationChallengeModel(
        id=challenge_id,
        email=req.email,
        code_digest=code_digest,
        expires_at=now + _EMAIL_CODE_TTL,
        attempts=0,
        resend_count=0,
        last_sent_at=now,
        created_at=now,
    )
    new_user_id = new_user.id
    try:
        auth_bind = db.get_bind()
    except Exception:
        auth_bind = None
    db.add_all([new_user, challenge])
    try:
        db.flush()
        db.commit()
    except IntegrityError as exc:
        _rollback_auth_safely(db, "register")
        raise HTTPException(status_code=409, detail="Username or email already exists.") from exc
    except OperationalError as exc:
        _rollback_auth_safely(db, "register")
        persisted = _verify_pending_registration(
            auth_bind, new_user_id, challenge_id, req.email, code_digest
        )
        if persisted is not True:
            if persisted is None:
                logger.critical(
                    "Registration commit outcome is uncertain; verification email was not sent.",
                    extra={"registration_state_unknown": True},
                )
            raise HTTPException(
                status_code=503, detail="Registration storage is busy; retry shortly."
            ) from exc
        logger.critical(
            "Registration commit raised after user and challenge were persisted; continuing verified email delivery.",
            extra={"registration_commit_error_after_persist": True},
        )

    try:
        send_registration_otp(req.email, code)
    except EmailDeliveryError as exc:
        try:
            _discard_pending_registration(auth_bind, new_user_id, challenge_id, req.email)
        except Exception as cleanup_error:
            logger.critical(
                "Registration email failed and pending account cleanup did not complete.",
                extra={
                    "registration_email_compensation_failure": True,
                    "cleanup_error_type": type(cleanup_error).__name__,
                },
            )
        raise HTTPException(status_code=503, detail="Verification email is unavailable.") from exc

    return RegistrationResponse(email=req.email)


@router.post("/api/auth/verify-email")
def verify_registration_email(
    req: EmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _reserve_public_auth_attempt(request, db)
    challenge = (
        db.query(EmailVerificationChallengeModel)
        .filter(EmailVerificationChallengeModel.email == req.email)
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=400, detail="Verification request is invalid or expired.")
    if challenge.expires_at <= _utc_now_naive():
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=400, detail="Verification request is invalid or expired.")
    if challenge.attempts >= _EMAIL_CODE_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many verification attempts.")

    expected = _email_code_digest(req.email, req.code)
    if not hmac.compare_digest(challenge.code_digest, expected):
        challenge_id = challenge.id
        challenge_digest = challenge.code_digest
        # End the read transaction before the write so concurrent SQLite
        # readers can serialize their conditional increments without a
        # read-to-write lock upgrade or a lost ORM read-modify-write update.
        db.rollback()
        attempt_time = _utc_now_naive()
        try:
            incremented = db.execute(
                update(EmailVerificationChallengeModel)
                .where(
                    EmailVerificationChallengeModel.id == challenge_id,
                    EmailVerificationChallengeModel.email == req.email,
                    EmailVerificationChallengeModel.code_digest == challenge_digest,
                    EmailVerificationChallengeModel.expires_at > attempt_time,
                    EmailVerificationChallengeModel.attempts < _EMAIL_CODE_MAX_ATTEMPTS,
                )
                .values(
                    attempts=EmailVerificationChallengeModel.attempts + 1,
                )
            )
            if incremented.rowcount != 1:
                db.rollback()
                latest = (
                    db.query(EmailVerificationChallengeModel)
                    .filter_by(id=challenge_id, email=req.email)
                    .first()
                )
                if (
                    latest is None
                    or latest.code_digest != challenge_digest
                    or latest.expires_at <= _utc_now_naive()
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="Verification request is invalid or expired.",
                    )
                if latest.attempts >= _EMAIL_CODE_MAX_ATTEMPTS:
                    raise HTTPException(status_code=429, detail="Too many verification attempts.")
                raise HTTPException(
                    status_code=503,
                    detail="Verification storage is temporarily unavailable.",
                )
            db.commit()
        except OperationalError as exc:
            _rollback_auth_safely(db, "verify_email_attempt")
            raise HTTPException(
                status_code=503,
                detail="Verification storage is busy; retry shortly.",
            ) from exc

        current_attempts = (
            db.query(EmailVerificationChallengeModel.attempts)
            .filter_by(id=challenge_id, email=req.email, code_digest=challenge_digest)
            .scalar()
        )
        if current_attempts is None:
            raise HTTPException(status_code=400, detail="Verification request is invalid or expired.")
        if current_attempts >= _EMAIL_CODE_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many verification attempts.")
        raise HTTPException(status_code=400, detail="Verification request is invalid or expired.")

    user = (
        db.query(UserModel)
        .filter(func.lower(UserModel.email) == req.email)
        .first()
    )
    if not user or user.email_verified:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=400, detail="Verification request is invalid or expired.")

    user.email_verified = True
    user_id = user.id
    challenge_id = challenge.id
    db.add(
        AuditLogModel(
            entity_name="auth",
            entity_id=user.id,
            action_type="EMAIL_VERIFIED",
            actor_id=user.id,
            details={"email_verified": True},
            timestamp=datetime.now(UTC),
        )
    )
    db.delete(challenge)
    try:
        bind = db.get_bind()
    except Exception:
        bind = None
    try:
        db.commit()
    except Exception as exc:
        _rollback_auth_safely(db, "verify_email")
        persisted = _verify_email_confirmation_commit(bind, user_id, challenge_id)
        if isinstance(persisted, dict):
            logger.critical(
                "Email verification commit raised after account activation state and audit were persisted.",
                extra={"email_verification_commit_error_after_persist": True},
            )
            return {
                "status": "VERIFIED",
                "email_verified": True,
                "activation_pending": persisted["activation_pending"],
            }
        if persisted is None:
            logger.critical(
                "Email verification commit outcome is uncertain.",
                extra={"email_verification_state_unknown": True},
            )
        if isinstance(exc, OperationalError):
            raise HTTPException(status_code=503, detail="Email verification storage is busy; retry shortly.") from exc
        raise
    return {"status": "VERIFIED", "email_verified": True, "activation_pending": not user.is_active}


@router.post("/api/auth/resend-verification")
def resend_registration_email(
    req: ResendEmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _reserve_public_auth_attempt(request, db)
    # Keep the response indistinguishable for unknown and already-verified addresses.
    generic_response = {"status": "ACCEPTED"}
    user = (
        db.query(UserModel)
        .filter(func.lower(UserModel.email) == req.email)
        .first()
    )
    if not user or user.email_verified:
        return generic_response
    challenge = (
        db.query(EmailVerificationChallengeModel)
        .filter(EmailVerificationChallengeModel.email == req.email)
        .first()
    )
    if not challenge:
        return generic_response

    now = _utc_now_naive()
    elapsed = now - challenge.last_sent_at
    if elapsed < _EMAIL_CODE_RESEND_DELAY:
        return generic_response
    if challenge.resend_count >= _EMAIL_CODE_MAX_RESENDS:
        return generic_response

    challenge_id = challenge.id
    code = _new_email_code()
    code_digest = _email_code_digest(req.email, code)
    new_resend_count = challenge.resend_count + 1
    expires_at = now + _EMAIL_CODE_TTL
    cutoff = now - _EMAIL_CODE_RESEND_DELAY
    try:
        bind = db.get_bind()
    except Exception:
        bind = None

    try:
        rows_updated = db.execute(
            update(EmailVerificationChallengeModel)
            .where(
                EmailVerificationChallengeModel.id == challenge_id,
                EmailVerificationChallengeModel.email == req.email,
                EmailVerificationChallengeModel.last_sent_at <= cutoff,
                EmailVerificationChallengeModel.resend_count < _EMAIL_CODE_MAX_RESENDS,
            )
            .values(
                code_digest=code_digest,
                expires_at=expires_at,
                attempts=0,
                resend_count=new_resend_count,
                last_sent_at=now,
            )
        ).rowcount
        if rows_updated != 1:
            _rollback_auth_safely(db, "resend_verification")
            return generic_response
        db.commit()
    except Exception as exc:
        _rollback_auth_safely(db, "resend_verification")
        persisted = _verify_resend_challenge_commit(
            bind,
            challenge_id,
            req.email,
            code_digest,
            new_resend_count,
            now,
            expires_at,
        )
        if persisted is not True:
            if persisted is None:
                logger.critical(
                    "Verification resend commit outcome is uncertain; new code was not sent.",
                    extra={"verification_resend_state_unknown": True},
                )
            if isinstance(exc, OperationalError):
                raise HTTPException(
                    status_code=503, detail="Verification resend storage is busy; retry shortly."
                ) from exc
            raise
        logger.critical(
            "Verification resend commit raised after the new challenge was persisted.",
            extra={"verification_resend_commit_error_after_persist": True},
        )

    try:
        send_registration_otp(req.email, code)
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail="Verification email is unavailable.") from exc
    return generic_response


@router.get("/api/auth/users", response_model=list[UserProfile])
def get_system_users(
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    is_global = getattr(current_user, "is_global_admin", False) and not current_user.facility_id
    query = db.query(UserModel)
    if not is_global:
        if not current_user.facility_id:
            raise HTTPException(status_code=403, detail="Tài khoản chưa được gán cơ sở y tế.")
        query = query.filter(UserModel.facility_id == current_user.facility_id)
    return [UserProfile.model_validate(user, from_attributes=True) for user in query.all()]


@router.get("/api/auth/current-user", response_model=UserProfile)
def get_current_user_profile(user: UserModel = Depends(get_current_user)):
    return UserProfile.model_validate(user, from_attributes=True)


def create_reset_token(
    username: str,
    expires_delta: timedelta | None = None,
    *,
    token_version: int = 1,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "purpose": "reset_password",
        "jti": str(uuid.uuid4()),
        "token_version": token_version,
        "exp": now + (expires_delta or timedelta(hours=1)),
        "iat": now,
    }
    return jwt.encode(payload, _signing_key(), algorithm=JWT_ALGORITHM)


@router.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Accept password recovery request."""
    _reserve_public_auth_attempt(request, db)
    try:
        ensure_password_reset_delivery_configured()
    except EmailDeliveryError as exc:
        raise HTTPException(status_code=503, detail="Password recovery email is unavailable.") from exc

    username = payload.username.strip().lower()
    _reserve_auth_attempt(username, db, namespace="password-reset")
    user = db.query(UserModel).filter(UserModel.username == username).first() if username else None
    if user and user.email and user.email_verified:
        token = create_reset_token(
            user.username,
            token_version=getattr(user, "token_version", 1) or 1,
        )
        try:
            send_password_reset_email(user.email, token)
        except EmailDeliveryError as exc:
            raise HTTPException(status_code=503, detail="Password recovery email is unavailable.") from exc
    return {
        "status": "SUCCESS",
        "message": "Nếu tài khoản tồn tại, yêu cầu đặt lại mật khẩu đã được tiếp nhận.",
    }


@router.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Reset account password via secure token."""
    _reserve_public_auth_attempt(request, db)
    raw_username = payload.username
    raw_token = payload.token
    username = raw_username.strip().lower() if isinstance(raw_username, str) else ""
    token = raw_token.strip() if isinstance(raw_token, str) else ""
    new_pw = payload.new_password or ""

    if not token:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu không được để trống.")
    if not isinstance(new_pw, str) or len(new_pw) < 6:
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

    token_id = data.get("jti")
    if not isinstance(token_id, str) or not token_id:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu không hợp lệ.")

    user = db.query(UserModel).filter(UserModel.username == target_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người dùng.")
    token_version = getattr(user, "token_version", 1) or 1
    if data.get("token_version") != token_version:
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

    db.add(ConsumedPasswordResetTokenModel(token_id=token_id, username=target_username))
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu đã được sử dụng.") from exc

    user.password_hash = hash_password(new_pw)
    user.must_change_password = False
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
    try:
        bind = db.get_bind()
    except Exception:
        bind = None
    try:
        db.commit()
    except IntegrityError as exc:
        _rollback_auth_safely(db, "reset_password")
        raise HTTPException(status_code=400, detail="Token đặt lại mật khẩu đã được sử dụng.") from exc
    except Exception as exc:
        _rollback_auth_safely(db, "reset_password")
        persisted = _verify_password_reset_commit(
            bind, token_id, target_username, token_version, new_pw
        )
        if persisted is True:
            logger.critical(
                "Password reset commit raised after the password, revocation and consumed-token record were persisted.",
                extra={"password_reset_commit_error_after_persist": True},
            )
            return {"status": "SUCCESS", "message": "Mật khẩu đã được đặt lại thành công."}
        if persisted is None:
            logger.critical(
                "Password reset commit outcome is uncertain.",
                extra={"password_reset_state_unknown": True},
            )
        if isinstance(exc, OperationalError):
            raise HTTPException(status_code=503, detail="Password reset storage is busy; retry shortly.") from exc
        raise
    return {"status": "SUCCESS", "message": "Mật khẩu đã được đặt lại thành công."}


@router.post("/api/auth/change-password", response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow logged in user to update clinical credentials."""
    old_pw = payload.old_password or payload.current_password or ""
    new_pw = payload.new_password
    if not new_pw:
        raise HTTPException(status_code=400, detail="Mật khẩu mới không được để trống")
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 6 ký tự")
    if payload.confirmation is not None and payload.confirmation != new_pw:
        raise HTTPException(status_code=422, detail="Xác nhận mật khẩu mới không khớp.")

    if user.password_hash:
        if not verify_password(old_pw, user.password_hash):
            raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")
    else:
        password_variable = "APP_ADMIN_PASSWORD" if user.role == "ADMIN" else "APP_DOCTOR_PASSWORD"
        configured_password = os.environ.get(password_variable)
        if not configured_password or not secrets.compare_digest(old_pw, configured_password):
            raise HTTPException(status_code=400, detail="Mật khẩu cũ không chính xác")

    user.password_hash = hash_password(new_pw)
    user.must_change_password = False
    user.tokens_revoked_at = datetime.now(UTC)
    user.token_version = (getattr(user, "token_version", 1) or 1) + 1
    db.commit()
    return TokenResponse(
        access_token=create_access_token({
            "sub": user.username,
            "uid": user.id,
            "token_version": user.token_version,
        }),
        user=UserProfile.model_validate(user, from_attributes=True),
        must_change_password=False,
    )


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
