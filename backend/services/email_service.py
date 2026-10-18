"""Small SMTP sender for registration verification messages."""

import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailDeliveryError(RuntimeError):
    """Raised when the application cannot send a registration email."""


def send_registration_otp(recipient: str, code: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    if not host or not sender:
        raise EmailDeliveryError("Email chưa được cấu hình trên máy chủ.")
    if bool(username) != bool(password):
        raise EmailDeliveryError("Cấu hình xác thực SMTP chưa đầy đủ.")
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        raise EmailDeliveryError("Cấu hình cổng SMTP không hợp lệ.") from None

    message = EmailMessage()
    message["Subject"] = "Mã xác minh đăng ký Vinmec"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Mã xác minh email đăng ký tài khoản bác sĩ của bạn là: {code}\n\n"
        "Mã có hiệu lực trong 10 phút. Nếu bạn không yêu cầu đăng ký, hãy bỏ qua email này."
    )

    try:
        with smtplib.SMTP(host, port, timeout=10) as client:
            client.starttls(context=ssl.create_default_context())
            if username:
                client.login(username, password)
            client.send_message(message)
    except Exception:
        raise EmailDeliveryError("Không thể gửi email xác minh. Vui lòng thử lại sau.") from None
