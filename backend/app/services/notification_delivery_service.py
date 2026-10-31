import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_settings import (
    NotificationReminderRule,
    NotificationSenderSetting,
)
from app.services.notification_email_service import (
    NotificationEmailService,
    retry_at,
)
from app.services.notification_preference_service import (
    NotificationPreferenceService,
)

logger = logging.getLogger("brightloop.notifications.delivery")


class NotificationDeliveryService:
    @staticmethod
    def enqueue(
        db: Session,
        *,
        customer_id: uuid.UUID,
        notification_type: str,
        title: str,
        values: dict[str, str],
        recipient_email: Optional[str],
        related_entity_type: Optional[str],
        related_entity_id: Optional[uuid.UUID],
        idempotency_key: str,
        settings: Settings,
        essential: bool = False,
    ) -> Optional[Notification]:
        existing = db.scalar(
            select(Notification).where(Notification.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

        if not essential and not NotificationEmailService.category_enabled(
            db, notification_type
        ):
            return None

        in_app_enabled = essential or NotificationPreferenceService.should_send_notification(
            db,
            customer_id,
            notification_type,
            "in_app",
            commit_preference=False,
        )
        email_enabled = essential or NotificationPreferenceService.should_send_notification(
            db,
            customer_id,
            notification_type,
            "email",
            commit_preference=False,
        )
        if not in_app_enabled and not email_enabled:
            return None

        subject, html_body, text_body = NotificationEmailService.render(
            db, notification_type, values
        )
        channel = "in_app" if in_app_enabled else "email"
        notification = Notification(
            customer_id=customer_id,
            title=title,
            message=text_body,
            notification_type=notification_type,
            channel=channel,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            status="pending" if email_enabled else "delivered",
            idempotency_key=idempotency_key,
            essential=essential,
        )
        db.add(notification)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(Notification).where(
                    Notification.idempotency_key == idempotency_key
                )
            )
            if existing is None:
                raise
            return existing

        if in_app_enabled:
            now = datetime.now(timezone.utc)
            db.add(
                NotificationDelivery(
                    notification_id=notification.id,
                    channel="in_app",
                    delivery_status="delivered",
                    sent_at=now,
                    delivered_at=now,
                )
            )
        if email_enabled:
            delivery = NotificationDelivery(
                notification_id=notification.id,
                channel="email",
                delivery_status="pending",
                recipient_email=recipient_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
            db.add(delivery)
            db.flush()

        db.commit()
        db.refresh(notification)
        if email_enabled:
            delivery = db.scalar(
                select(NotificationDelivery).where(
                    NotificationDelivery.notification_id == notification.id,
                    NotificationDelivery.channel == "email",
                )
            )
            if delivery is not None:
                NotificationDeliveryService.dispatch_email(db, delivery.id, settings)
        return notification

    @staticmethod
    def dispatch_email(
        db: Session, delivery_id: uuid.UUID, settings: Settings
    ) -> NotificationDelivery:
        delivery = db.scalar(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .with_for_update()
        )
        if delivery is None:
            raise LookupError(f"Notification delivery {delivery_id} not found")
        if delivery.delivery_status in {"sent", "delivered", "cancelled"}:
            return delivery
        now = datetime.now(timezone.utc)
        if delivery.next_retry_at is not None:
            retry_time = delivery.next_retry_at
            if retry_time.tzinfo is None:
                retry_time = retry_time.replace(tzinfo=timezone.utc)
            if retry_time > now:
                return delivery
        if delivery.attempt_count >= settings.NOTIFICATION_MAX_ATTEMPTS:
            return delivery

        notification = db.get(Notification, delivery.notification_id)
        if notification is None:
            delivery.delivery_status = "cancelled"
            db.commit()
            return delivery
        if notification.notification_type in {"invoice_due", "payment_overdue"}:
            if not NotificationDeliveryService._invoice_is_payable(
                db, notification.related_entity_id
            ):
                NotificationDeliveryService.cancel_notification(db, notification)
                db.commit()
                return delivery

        delivery.attempt_count += 1
        try:
            sender_setting = db.get(NotificationSenderSetting, 1)
            sender = (
                f"{sender_setting.sender_name} <{sender_setting.sender_email}>"
                if sender_setting is not None
                else settings.RESEND_FROM
            )
            provider_id = NotificationEmailService.send(
                settings, delivery, sender=sender
            )
        except Exception as exc:
            delivery.delivery_status = "failed"
            delivery.failed_at = now
            delivery.error_message = str(exc)[:4000]
            delivery.next_retry_at = (
                retry_at(
                    now,
                    delivery.attempt_count,
                    settings.NOTIFICATION_RETRY_DELAY_MINUTES,
                )
                if delivery.attempt_count < settings.NOTIFICATION_MAX_ATTEMPTS
                else None
            )
            notification.status = "failed"
            logger.exception(
                "Email notification delivery failed (delivery_id=%s)",
                delivery.id,
            )
        else:
            delivery.delivery_status = "sent"
            delivery.provider_message_id = provider_id
            delivery.sent_at = now
            delivery.failed_at = None
            delivery.error_message = None
            delivery.next_retry_at = None
            notification.status = "sent"
        db.commit()
        db.refresh(delivery)
        return delivery

    @staticmethod
    def retry_failed(
        db: Session, delivery_id: uuid.UUID, settings: Settings
    ) -> NotificationDelivery:
        delivery = db.get(NotificationDelivery, delivery_id)
        if delivery is None:
            raise LookupError(f"Notification delivery {delivery_id} not found")
        if delivery.delivery_status != "failed":
            raise ValueError("Only failed notification deliveries can be retried")
        delivery.next_retry_at = None
        delivery.attempt_count = min(
            delivery.attempt_count, max(0, settings.NOTIFICATION_MAX_ATTEMPTS - 1)
        )
        db.commit()
        return NotificationDeliveryService.dispatch_email(db, delivery_id, settings)

    @staticmethod
    def cancel_notification(db: Session, notification: Notification) -> None:
        notification.status = "cancelled"
        for delivery in notification.deliveries:
            if delivery.delivery_status in {"pending", "failed"}:
                delivery.delivery_status = "cancelled"
                delivery.next_retry_at = None

    @staticmethod
    def cancel_invoice_reminders(db: Session, invoice_id: uuid.UUID) -> int:
        notifications = list(
            db.scalars(
                select(Notification)
                .join(
                    NotificationDelivery,
                    NotificationDelivery.notification_id == Notification.id,
                )
                .where(
                    Notification.related_entity_type == "invoice",
                    Notification.related_entity_id == invoice_id,
                    Notification.notification_type.in_(
                        ["invoice_due", "payment_overdue"]
                    ),
                    NotificationDelivery.channel == "email",
                    NotificationDelivery.delivery_status.in_(["pending", "failed"]),
                )
                .with_for_update()
            ).all()
        )
        for notification in notifications:
            NotificationDeliveryService.cancel_notification(db, notification)
        db.commit()
        return len(notifications)

    @staticmethod
    def _invoice_is_payable(db: Session, invoice_id: Optional[uuid.UUID]) -> bool:
        if invoice_id is None:
            return False
        from app.modules.billing.models import Invoice

        invoice = db.scalar(
            select(Invoice).where(Invoice.id == invoice_id).with_for_update()
        )
        return bool(
            invoice is not None
            and invoice.status == "confirmed"
            and invoice.outstanding > 0
        )

    @staticmethod
    def get_active_rules(db: Session) -> list[NotificationReminderRule]:
        return list(
            db.scalars(
                select(NotificationReminderRule).where(
                    NotificationReminderRule.is_active.is_(True)
                )
            ).all()
        )
