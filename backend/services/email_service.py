"""Small SMTP sender for account verification and password recovery."""

import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode, urlsplit


class EmailDeliveryError(RuntimeError):
    """Raised when email delivery is unavailable or misconfigured."""


def _smtp_settings() -> tuple[str, str, str, str, int]:
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    if not host or not sender:
        raise EmailDeliveryError("Email delivery is not configured.")
    if bool(username) != bool(password):
        raise EmailDeliveryError("SMTP authentication settings are incomplete.")
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise EmailDeliveryError("SMTP port is invalid.") from None
    return host, sender, username, password, port


def ensure_password_reset_delivery_configured() -> None:
    _smtp_settings()
    public_url = os.environ.get("APP_PUBLIC_URL", "").strip()
    parsed = urlsplit(public_url)
    local_http = parsed.scheme == "http" and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if (
        not parsed.netloc
        or parsed.username is not None
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not local_http)
    ):
        raise EmailDeliveryError("APP_PUBLIC_URL must be an HTTPS application URL.")


def _send_message(message: EmailMessage) -> None:
    host, sender, username, password, port = _smtp_settings()
    message["From"] = sender
    try:
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.starttls(context=ssl.create_default_context())
            if username:
                client.login(username, password)
            client.send_message(message)
    except Exception:
        raise EmailDeliveryError("Email delivery failed.") from None


def send_registration_otp(recipient: str, code: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Account email verification code"
    message["To"] = recipient
    message.set_content(
        f"Your account verification code is: {code}\n\n"
        "The code expires in 10 minutes. If you did not request registration, ignore this message."
    )
    _send_message(message)


def send_password_reset_email(recipient: str, token: str) -> None:
    ensure_password_reset_delivery_configured()
    public_url = os.environ["APP_PUBLIC_URL"].strip().rstrip("/")
    reset_url = f"{public_url}/#reset?{urlencode({'token': token})}"

    message = EmailMessage()
    message["Subject"] = "Password reset instructions"
    message["To"] = recipient
    message.set_content(
        "Use this one-time link to reset your account password. It expires in one hour:\n\n"
        f"{reset_url}\n\n"
        "If you did not request a reset, ignore this message."
    )
    _send_message(message)
