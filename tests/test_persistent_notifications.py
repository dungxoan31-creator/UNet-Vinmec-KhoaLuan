import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from datetime import datetime, UTC
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    FacilityModel,
    NotificationModel,
    SessionLocal,
    StudyModel,
    UserModel,
)


@pytest.fixture
def notif_env():
    prefix = uuid.uuid4().hex[:8]
    test_db = SessionLocal()

    fac = FacilityModel(
        id=f"FAC-{prefix}",
        name=f"Facility {prefix}",
        facility_code=f"F-{prefix}",
        is_active=True,
    )
    test_db.add(fac)
    test_db.commit()

    pwd_hash = hash_password("SecurePass123!")

    user_a = UserModel(
        id=f"user-a-{prefix}",
        username=f"user_a_{prefix}",
        full_name="User Alpha",
        role="DOCTOR",
        facility_id=fac.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    user_b = UserModel(
        id=f"user-b-{prefix}",
        username=f"user_b_{prefix}",
        full_name="User Beta",
        role="DOCTOR",
        facility_id=fac.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    test_db.add_all([user_a, user_b])
    test_db.commit()

    token_a = create_access_token({"sub": user_a.username, "role": "DOCTOR", "facility_id": fac.id})
    token_b = create_access_token({"sub": user_b.username, "role": "DOCTOR", "facility_id": fac.id})

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "user_a": user_a,
            "user_b": user_b,
            "token_a": token_a,
            "token_b": token_b,
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_user_only_sees_own_notifications(notif_env):
    """GET /api/notifications only returns notifications for the authenticated user."""
    client = notif_env["client"]
    db = notif_env["db"]
    user_a = notif_env["user_a"]
    user_b = notif_env["user_b"]
    token_a = notif_env["token_a"]
    token_b = notif_env["token_b"]
    prefix = notif_env["prefix"]

    notif_a1 = NotificationModel(
        id=f"n-a1-{prefix}",
        recipient_id=user_a.id,
        event_type="CASE_ASSIGNED",
        title="Notice A1",
        message="Message for A1",
        is_read=False,
        created_at=datetime.now(UTC),
    )
    notif_b1 = NotificationModel(
        id=f"n-b1-{prefix}",
        recipient_id=user_b.id,
        event_type="CORRECTION_REQUESTED",
        title="Notice B1",
        message="Message for B1",
        is_read=False,
        created_at=datetime.now(UTC),
    )
    db.add_all([notif_a1, notif_b1])
    db.commit()

    # User A calls GET /api/notifications
    resp_a = client.get("/api/notifications", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200, resp_a.text
    items_a = resp_a.json()
    ids_a = [item["id"] for item in items_a]
    assert notif_a1.id in ids_a
    assert notif_b1.id not in ids_a

    # User B calls GET /api/notifications
    resp_b = client.get("/api/notifications", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200, resp_b.text
    items_b = resp_b.json()
    ids_b = [item["id"] for item in items_b]
    assert notif_b1.id in ids_b
    assert notif_a1.id not in ids_b


def test_notifications_read_only_updates_own(notif_env):
    """POST /api/notifications/read only marks own notifications as read and returns actual count."""
    client = notif_env["client"]
    db = notif_env["db"]
    user_a = notif_env["user_a"]
    user_b = notif_env["user_b"]
    token_a = notif_env["token_a"]
    token_b = notif_env["token_b"]
    prefix = notif_env["prefix"]

    notif_a = NotificationModel(
        id=f"n-read-a-{prefix}",
        recipient_id=user_a.id,
        event_type="CASE_ASSIGNED",
        title="Notice A",
        message="Message A",
        is_read=False,
        created_at=datetime.now(UTC),
    )
    db.add(notif_a)
    db.commit()

    # User B attempts to mark User A's notification as read
    resp_b_hack = client.post(
        "/api/notifications/read",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"ids": [notif_a.id]},
    )
    assert resp_b_hack.status_code == 200, resp_b_hack.text
    assert resp_b_hack.json()["updated"] == 0, "User B must not be able to mark User A's notification as read"

    db.refresh(notif_a)
    assert notif_a.is_read is False, "Notification must remain unread"

    # User A marks their own notification as read
    resp_a_read = client.post(
        "/api/notifications/read",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"ids": [notif_a.id]},
    )
    assert resp_a_read.status_code == 200, resp_a_read.text
    assert resp_a_read.json()["updated"] == 1

    db.refresh(notif_a)
    assert notif_a.is_read is True
    assert notif_a.read_at is not None

    # Marking already read notifications again returns updated: 0 (idempotent)
    resp_a_repeat = client.post(
        "/api/notifications/read",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"ids": [notif_a.id]},
    )
    assert resp_a_repeat.status_code == 200
    assert resp_a_repeat.json()["updated"] == 0
