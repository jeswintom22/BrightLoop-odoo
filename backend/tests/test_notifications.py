import uuid

import pytest
from fastapi.testclient import TestClient

from app import deps
from app.core.database import Base
from app.core.errors import AppError
from app.deps import CurrentUser
from app.main import create_app
from app.models.notification import Notification
from app.services.notification_preference_service import (
    NotificationPreferenceService,
    should_send_notification,
)
from app.services.notification_service import NotificationService


CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")
OTHER_CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000102")


@pytest.fixture
def notification_client(session_factory):
    app = create_app()

    def test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = test_db
    app.dependency_overrides[deps.get_current_user] = lambda: CurrentUser(
        id=CUSTOMER_ID, email="customer@example.com"
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_notification(db, customer_id=CUSTOMER_ID, **overrides):
    values = {
        "title": "Payment Reminder",
        "message": "Your payment is due soon.",
        "notification_type": "payment_due",
    }
    values.update(overrides)
    return NotificationService.create_notification(
        db, customer_id=customer_id, **values
    )


def test_notification_create_list_and_filters(session, notification_client):
    unread = _create_notification(session)
    read = _create_notification(
        session, notification_type="invoice_due", title="Invoice due"
    )
    NotificationService.mark_read(session, CUSTOMER_ID, read.id)
    _create_notification(session, customer_id=OTHER_CUSTOMER_ID)

    response = notification_client.get("/api/v1/notifications?page=1&page_size=1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["page"] == 1
    assert body["page_size"] == 1

    response = notification_client.get(
        "/api/v1/notifications?notification_type=invoice_due&is_read=true"
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(read.id)]
    assert response.json()["items"][0]["is_read"] is True
    assert unread.id != read.id


def test_notification_details_and_ownership(session, notification_client):
    own = _create_notification(session)
    other = _create_notification(session, customer_id=OTHER_CUSTOMER_ID)

    assert notification_client.get(
        f"/api/v1/notifications/{own.id}"
    ).status_code == 200
    response = notification_client.get(f"/api/v1/notifications/{other.id}")
    assert response.status_code == 404


def test_unread_count_mark_read_and_mark_all(session, notification_client):
    first = _create_notification(session)
    second = _create_notification(session, title="Another reminder")
    _create_notification(session, customer_id=OTHER_CUSTOMER_ID)

    response = notification_client.get("/api/v1/notifications/unread-count")
    assert response.json() == {"unread_count": 2}

    response = notification_client.patch(
        f"/api/v1/notifications/{first.id}/read"
    )
    assert response.status_code == 200
    assert response.json()["is_read"] is True
    assert response.json()["read_at"] is not None
    assert response.json()["status"] == "read"

    # Repeating the operation is safe and does not change ownership.
    assert notification_client.patch(
        f"/api/v1/notifications/{first.id}/read"
    ).status_code == 200

    response = notification_client.patch("/api/v1/notifications/read-all")
    assert response.status_code == 200
    assert response.json() == {"updated_count": 1}
    assert notification_client.get(
        "/api/v1/notifications/unread-count"
    ).json() == {"unread_count": 0}
    session.expire_all()
    assert NotificationService.get_notification(
        session, CUSTOMER_ID, second.id
    ).is_read


def test_delete_notification_is_scoped_to_customer(session, notification_client):
    own = _create_notification(session)
    other = _create_notification(session, customer_id=OTHER_CUSTOMER_ID)
    own_id = own.id
    other_id = other.id

    assert notification_client.delete(
        f"/api/v1/notifications/{own_id}"
    ).status_code == 204
    session.expire_all()
    assert session.get(Notification, own_id) is None
    assert notification_client.delete(
        f"/api/v1/notifications/{other_id}"
    ).status_code == 404
    assert session.get(Notification, other_id) is not None


def test_preferences_defaults_update_and_customer_isolation(
    session, notification_client
):
    response = notification_client.get("/api/v1/notification-preferences")
    assert response.status_code == 200
    assert response.json()["customer_id"] == str(CUSTOMER_ID)
    assert response.json()["email_enabled"] is True
    assert response.json()["in_app_enabled"] is True

    data = {
        "email_enabled": False,
        "in_app_enabled": True,
        "payment_due_enabled": False,
        "invoice_due_enabled": True,
        "overdue_enabled": True,
        "renewal_enabled": True,
        "payment_confirmation_enabled": True,
        "invoice_generated_enabled": True,
    }
    response = notification_client.put(
        "/api/v1/notification-preferences",
        json={**data, "customer_id": str(OTHER_CUSTOMER_ID)},
    )
    assert response.status_code == 422
    response = notification_client.put(
        "/api/v1/notification-preferences", json=data
    )
    assert response.status_code == 200
    assert response.json()["customer_id"] == str(CUSTOMER_ID)
    assert response.json()["email_enabled"] is False
    assert response.json()["payment_due_enabled"] is False

    other = NotificationPreferenceService.get_or_create(
        session, OTHER_CUSTOMER_ID
    )
    assert other.email_enabled is True
    assert other.payment_due_enabled is True


def test_should_send_notification_checks_channel_and_category(session):
    prefs = NotificationPreferenceService.get_or_create(session, CUSTOMER_ID)
    prefs.email_enabled = False
    prefs.payment_due_enabled = False
    session.commit()

    assert not should_send_notification(
        session, CUSTOMER_ID, "payment_due", "email"
    )
    assert not should_send_notification(
        session, CUSTOMER_ID, "payment_due", "in_app"
    )
    assert should_send_notification(
        session, CUSTOMER_ID, "invoice_due", "in_app"
    )


def test_invalid_notification_preference_type_rejected(session):
    with pytest.raises(AppError) as exc_info:
        should_send_notification(
            session, CUSTOMER_ID, "unknown_type", "in_app"
        )
    assert exc_info.value.code == "INVALID_NOTIFICATION_SETTING"


def test_notification_migration_model_metadata_registered():
    assert "notifications" in Base.metadata.tables
    assert "notification_preferences" in Base.metadata.tables
    assert "notification_deliveries" in Base.metadata.tables
