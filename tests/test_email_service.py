import importlib

import pytest


ENV_NAMES = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM",
)


class FakeSMTP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.events = []
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def starttls(self, **_kwargs):
        self.events.append("starttls")

    def login(self, username, password):
        self.events.append(("login", username, password))

    def send_message(self, message):
        self.events.append("send")
        self.message = message


def _clear_smtp_env(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def _configure_smtp(monkeypatch, *, credentials=False):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.org")
    monkeypatch.setenv("SMTP_PORT", "2525")
    if credentials:
        monkeypatch.setenv("SMTP_USERNAME", "mailer")
        monkeypatch.setenv("SMTP_PASSWORD", "sensitive-password")


@pytest.mark.parametrize("missing", ("SMTP_HOST", "SMTP_FROM"))
def test_missing_smtp_settings_do_not_send(monkeypatch, missing):
    service = importlib.import_module("backend.services.email_service")
    _clear_smtp_env(monkeypatch)
    _configure_smtp(monkeypatch)
    monkeypatch.delenv(missing)
    calls = []
    monkeypatch.setattr(service.smtplib, "SMTP", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(service.EmailDeliveryError):
        service.send_registration_otp("doctor@example.org", "001234")
    assert calls == []


def test_send_registration_otp_uses_starttls(monkeypatch):
    service = importlib.import_module("backend.services.email_service")
    _clear_smtp_env(monkeypatch)
    _configure_smtp(monkeypatch)
    smtp = FakeSMTP("smtp.example.org", 2525, 10)
    monkeypatch.setattr(service.smtplib, "SMTP", lambda host, port, timeout: smtp)

    service.send_registration_otp("doctor@example.org", "001234")

    assert (smtp.host, smtp.port, smtp.timeout) == ("smtp.example.org", 2525, 10)
    assert smtp.events == ["starttls", "send"]
    assert smtp.message["To"] == "doctor@example.org"
    assert "001234" in smtp.message.get_content()


def test_smtp_auth_requires_both_credentials(monkeypatch):
    service = importlib.import_module("backend.services.email_service")
    _clear_smtp_env(monkeypatch)
    _configure_smtp(monkeypatch)
    monkeypatch.setenv("SMTP_USERNAME", "mailer")
    calls = []
    monkeypatch.setattr(service.smtplib, "SMTP", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(service.EmailDeliveryError):
        service.send_registration_otp("doctor@example.org", "001234")
    assert calls == []


def test_smtp_authentication_uses_configured_credentials(monkeypatch):
    service = importlib.import_module("backend.services.email_service")
    _clear_smtp_env(monkeypatch)
    _configure_smtp(monkeypatch, credentials=True)
    smtp = FakeSMTP("smtp.example.org", 2525, 10)
    monkeypatch.setattr(service.smtplib, "SMTP", lambda host, port, timeout: smtp)

    service.send_registration_otp("doctor@example.org", "001234")

    assert smtp.events == [
        "starttls",
        ("login", "mailer", "sensitive-password"),
        "send",
    ]


def test_smtp_failure_is_wrapped_without_credentials(monkeypatch):
    service = importlib.import_module("backend.services.email_service")
    _clear_smtp_env(monkeypatch)
    _configure_smtp(monkeypatch, credentials=True)

    class FailingSMTP(FakeSMTP):
        def send_message(self, message):
            raise RuntimeError("SMTP rejected sensitive-password")

    smtp = FailingSMTP("smtp.example.org", 2525, 10)
    monkeypatch.setattr(service.smtplib, "SMTP", lambda host, port, timeout: smtp)

    with pytest.raises(service.EmailDeliveryError) as error:
        service.send_registration_otp("doctor@example.org", "001234")
    assert "sensitive-password" not in str(error.value)
