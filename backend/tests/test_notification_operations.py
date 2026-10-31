import base64
import datetime as dt
import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from fastapi.testclient import TestClient

from app import deps
from app.core.config import Settings
from app.core.time import business_date
from app.deps import CurrentUser
from app.main import create_app
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_settings import (
    NotificationReminderRule,
)
from app.services.notification_delivery_service import NotificationDeliveryService
from app.services.notification_email_service import NotificationEmailService
from app.services.notification_event_service import (
    notify_invoice_generated,
    notify_payment_confirmed,
)
from app.services.notification_preference_service import (
    NotificationPreferenceService,
)
from app.services.notification_scheduler_service import (
    process_scheduled_notifications,
)


def _record_accepted_email(db, delivery_id, settings):
    delivery = db.get(NotificationDelivery, delivery_id)
    notification = db.get(Notification, delivery.notification_id)
    delivery.attempt_count += 1
    delivery.delivery_status = "sent"
    delivery.provider_message_id = f"provider-{delivery.id}"
    notification.status = "sent"
    db.commit()
    return delivery


def test_optional_invoice_notification_respects_customer_preferences(
    session, providers, confirmed_invoice
):
    customer_id = confirmed_invoice.customer_id
    preference = NotificationPreferenceService.get_or_create(session, customer_id)
    preference.email_enabled = False
    preference.in_app_enabled = False
    session.commit()

    notify_invoice_generated(
        session,
        invoice=confirmed_invoice,
        customers=providers["customers"],
        settings=Settings(),
    )

    count = session.scalar(
        select(func.count(Notification.id)).where(
            Notification.related_entity_id == confirmed_invoice.id
        )
    )
    assert count == 0


def test_invoice_notification_suppressed_for_production_stub_customer(
    session, providers, confirmed_invoice
):
    notify_invoice_generated(
        session,
        invoice=confirmed_invoice,
        customers=providers["customers"],
        settings=Settings(ENVIRONMENT="production", USE_STUB_PROVIDERS=True),
    )
    count = session.scalar(
        select(func.count(Notification.id)).where(
            Notification.related_entity_id == confirmed_invoice.id
        )
    )
    assert count == 0


def test_payment_confirmation_is_idempotent(
    monkeypatch, session, providers, confirmed_invoice, payment_service
):
    monkeypatch.setattr(
        NotificationDeliveryService,
        "dispatch_email",
        staticmethod(_record_accepted_email),
    )
    payment, _ = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("10.00"),
        method="upi",
    )
    session.commit()

    for _ in range(2):
        notify_payment_confirmed(
            session,
            payment=payment,
            customers=providers["customers"],
            settings=Settings(),
        )

    notifications = session.scalars(
        select(Notification).where(
            Notification.idempotency_key == f"payment-confirmation:{payment.id}"
        )
    ).all()
    assert len(notifications) == 1
    delivery = session.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.notification_id == notifications[0].id,
            NotificationDelivery.channel == "email",
        )
    )
    assert delivery.delivery_status == "sent"
    assert "Remaining balance" in delivery.text_body


def test_due_reminder_is_idempotent_and_uses_remaining_balance(
    monkeypatch, session, providers, confirmed_invoice
):
    monkeypatch.setattr(
        NotificationDeliveryService,
        "dispatch_email",
        staticmethod(_record_accepted_email),
    )
    as_of = business_date()
    confirmed_invoice.due_date = as_of + dt.timedelta(days=1)
    confirmed_invoice.amount_paid = (
        confirmed_invoice.total_amount / 2
    ).quantize(Decimal("0.01"))
    session.add(
        NotificationReminderRule(
            notification_type="invoice_due",
            days_offset=1,
            is_active=True,
        )
    )
    session.commit()
    assert confirmed_invoice.status == "confirmed"
    assert confirmed_invoice.amount_paid < confirmed_invoice.total_amount
    assert confirmed_invoice.due_date == as_of + dt.timedelta(days=1)
    assert NotificationDeliveryService.get_active_rules(session)[0].days_offset == 1

    for attempt in range(2):
        result = process_scheduled_notifications(
            session,
            customers=providers["customers"],
            subscriptions=providers["subs"],
            pricing=providers["pricing"],
            settings=Settings(),
            as_of=as_of,
        )
        assert result["invoice_reminders"] == (1 if attempt == 0 else 0)

    notifications = session.scalars(
        select(Notification).where(
            Notification.related_entity_id == confirmed_invoice.id,
            Notification.notification_type == "invoice_due",
        )
    ).all()
    assert len(notifications) == 1
    delivery = session.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.notification_id == notifications[0].id,
            NotificationDelivery.channel == "email",
        )
    )
    assert f"INR {confirmed_invoice.outstanding:,.2f}" in delivery.text_body


def test_paid_invoice_cancels_pending_reminder_even_when_read(
    session, confirmed_invoice
):
    notification = Notification(
        customer_id=confirmed_invoice.customer_id,
        title="Due soon",
        message="Invoice reminder",
        notification_type="invoice_due",
        channel="in_app",
        related_entity_type="invoice",
        related_entity_id=confirmed_invoice.id,
        status="read",
        is_read=True,
        idempotency_key=f"test-reminder:{uuid.uuid4()}",
    )
    session.add(notification)
    session.flush()
    delivery = NotificationDelivery(
        notification_id=notification.id,
        channel="email",
        delivery_status="pending",
        recipient_email="customer@example.com",
        subject="Due",
    )
    session.add(delivery)
    confirmed_invoice.status = "paid"
    confirmed_invoice.amount_paid = confirmed_invoice.total_amount
    session.commit()

    assert NotificationDeliveryService.cancel_invoice_reminders(
        session, confirmed_invoice.id
    ) == 1
    assert notification.status == "cancelled"
    assert delivery.delivery_status == "cancelled"


def test_failed_delivery_can_be_retried(monkeypatch, session):
    notification = Notification(
        customer_id=uuid.uuid4(),
        title="Payment update",
        message="Payment received",
        notification_type="payment_confirmation",
        channel="email",
        status="failed",
        idempotency_key=f"retry:{uuid.uuid4()}",
        essential=True,
    )
    session.add(notification)
    session.flush()
    delivery = NotificationDelivery(
        notification_id=notification.id,
        channel="email",
        delivery_status="failed",
        attempt_count=1,
        recipient_email="customer@example.com",
        subject="Payment received",
        text_body="Received",
    )
    session.add(delivery)
    session.commit()

    monkeypatch.setattr(
        NotificationEmailService,
        "send",
        staticmethod(lambda settings, delivery, sender=None: "provider-retry"),
    )
    retried = NotificationDeliveryService.retry_failed(
        session, delivery.id, Settings(RESEND_API_KEY="test-key")
    )
    assert retried.delivery_status == "sent"
    assert retried.attempt_count == 2
    assert retried.provider_message_id == "provider-retry"


def test_production_stub_mode_never_claims_email_success(session):
    notification = Notification(
        customer_id=uuid.uuid4(),
        title="Payment update",
        message="Payment received",
        notification_type="payment_confirmation",
        channel="email",
        status="pending",
        idempotency_key=f"production-stub:{uuid.uuid4()}",
    )
    session.add(notification)
    session.flush()
    delivery = NotificationDelivery(
        notification_id=notification.id,
        channel="email",
        delivery_status="pending",
        recipient_email="customer@example.com",
        subject="Payment received",
    )
    session.add(delivery)
    session.commit()

    result = NotificationDeliveryService.dispatch_email(
        session,
        delivery.id,
        Settings(
            ENVIRONMENT="production",
            USE_STUB_PROVIDERS=True,
            RESEND_API_KEY="test-key",
        ),
    )

    assert result.delivery_status == "failed"
    assert result.provider_message_id is None
    assert "stub providers" in result.error_message


def _signed_webhook(payload: str, event_id: str, secret: bytes) -> tuple[str, str]:
    timestamp = str(int(time.time()))
    message = f"{event_id}.{timestamp}.{payload}".encode()
    signature = base64.b64encode(
        hmac.new(secret, message, hashlib.sha256).digest()
    ).decode()
    return timestamp, f"v1,{signature}"


def test_resend_webhook_tracks_delivery_and_ignores_out_of_order_status(
    session,
):
    notification = Notification(
        customer_id=uuid.uuid4(),
        title="Payment update",
        message="Payment received",
        notification_type="payment_confirmation",
        channel="email",
        status="sent",
        idempotency_key=f"webhook:{uuid.uuid4()}",
        essential=True,
    )
    session.add(notification)
    session.flush()
    delivery = NotificationDelivery(
        notification_id=notification.id,
        channel="email",
        delivery_status="sent",
        provider_message_id="provider-webhook",
        recipient_email="customer@example.com",
        subject="Payment received",
    )
    session.add(delivery)
    session.commit()

    signing_secret = b"webhook-test-secret"
    webhook_secret = base64.b64encode(signing_secret).decode()

    def apply(event_id, event_type):
        payload = json.dumps(
            {"type": event_type, "data": {"email_id": "provider-webhook"}}
        )
        timestamp, signature = _signed_webhook(
            payload, event_id, signing_secret
        )
        return NotificationEmailService.apply_webhook(
            session,
            raw_body=payload,
            event_id=event_id,
            timestamp=timestamp,
            signature=signature,
            webhook_secret=webhook_secret,
        )

    assert apply("evt-delivered", "email.delivered") is True
    assert apply("evt-delivered", "email.delivered") is True
    assert apply("evt-sent-late", "email.sent") is True
    assert delivery.delivery_status == "delivered"
    assert notification.status == "delivered"


def test_admin_can_update_schedules_categories_and_sender(session_factory):
    app = create_app()

    def test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = test_db
    app.dependency_overrides[deps.get_current_user] = lambda: CurrentUser(
        id=uuid.uuid4(), email="admin@example.com", roles=["admin"]
    )
    try:
        with TestClient(app) as client:
            rules = client.put(
                "/api/v1/admin/notifications/rules",
                json={
                    "items": [
                        {
                            "notification_type": "invoice_due",
                            "days_offset": 2,
                            "is_active": True,
                        },
                        {
                            "notification_type": "payment_overdue",
                            "days_offset": -5,
                            "is_active": False,
                        },
                    ]
                },
            )
            assert rules.status_code == 200
            assert len(rules.json()["items"]) == 2

            categories = client.put(
                "/api/v1/admin/notifications/categories",
                json={
                    "items": [
                        {
                            "notification_type": "invoice_generated",
                            "is_enabled": False,
                        }
                    ]
                },
            )
            assert categories.status_code == 200
            assert categories.json()["items"][0]["is_enabled"] is False

            sender = client.put(
                "/api/v1/admin/notifications/sender",
                json={
                    "sender_name": "Billing Team",
                    "sender_email": "billing@example.com",
                },
            )
            assert sender.status_code == 200
            assert sender.json()["sender_email"] == "billing@example.com"
    finally:
        app.dependency_overrides.clear()


def test_admin_notification_settings_reject_non_admin(session_factory):
    app = create_app()

    def test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = test_db
    app.dependency_overrides[deps.get_current_user] = lambda: CurrentUser(
        id=uuid.uuid4(), email="customer@example.com", roles=[]
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/notifications/rules")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_scheduled_notification_endpoints_require_internal_token(session_factory):
    app = create_app()

    def test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps.get_db] = test_db
    try:
        with TestClient(app) as client:
            path = "/api/v1/internal/notifications/retries"
            assert client.post(path).status_code == 403
            response = client.post(
                path, headers={"X-Internal-Token": "dev-internal-token"}
            )
        assert response.status_code == 200
        assert response.json() == {"retried": 0, "failed": 0}
    finally:
        app.dependency_overrides.clear()
