import datetime as dt
import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.billing.integrations import (
    CustomerProvider,
    PricingProvider,
    SubscriptionProvider,
)
from app.modules.billing.models import Invoice
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_settings import NotificationReminderRule
from app.services.notification_delivery_service import NotificationDeliveryService
from app.services.notification_event_service import notify_subscription_renewal

logger = logging.getLogger("brightloop.notifications.scheduler")


def _money(amount: Decimal, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _cancel_paid_invoice_reminders(db: Session) -> int:
    notifications = list(
        db.scalars(
            select(Notification)
            .join(
                NotificationDelivery,
                NotificationDelivery.notification_id == Notification.id,
            )
            .where(
                Notification.notification_type.in_(["invoice_due", "payment_overdue"]),
                NotificationDelivery.channel == "email",
                NotificationDelivery.delivery_status.in_(["pending", "failed"]),
            )
            .with_for_update()
        ).all()
    )
    cancelled = 0
    for notification in notifications:
        invoice = db.get(Invoice, notification.related_entity_id)
        if invoice is None or invoice.status != "confirmed" or invoice.outstanding <= 0:
            NotificationDeliveryService.cancel_notification(db, notification)
            cancelled += 1
    if cancelled:
        db.commit()
    return cancelled


def process_scheduled_notifications(
    db: Session,
    *,
    customers: CustomerProvider,
    subscriptions: SubscriptionProvider,
    pricing: PricingProvider,
    settings: Settings,
    as_of: dt.date,
    batch_size: int = 200,
) -> dict[str, int]:
    result = {
        "invoice_reminders": 0,
        "subscription_reminders": 0,
        "cancelled": _cancel_paid_invoice_reminders(db),
        "retried": 0,
        "failed": 0,
    }

    for rule in NotificationDeliveryService.get_active_rules(db):
        if rule.notification_type in {"invoice_due", "payment_overdue"}:
            due_date = as_of + dt.timedelta(days=rule.days_offset)
            offset = 0
            while True:
                invoices = list(
                    db.scalars(
                        select(Invoice)
                        .where(
                            Invoice.status == "confirmed",
                            Invoice.due_date == due_date,
                            Invoice.amount_paid < Invoice.total_amount,
                        )
                        .order_by(Invoice.id)
                        .offset(offset)
                        .limit(batch_size)
                        .with_for_update()
                    ).all()
                )
                if not invoices:
                    break
                offset += len(invoices)
                for invoice in invoices:
                    if invoice.outstanding <= 0:
                        continue
                    idempotency_key = (
                        f"scheduled-{rule.notification_type}:{invoice.id}:"
                        f"{rule.days_offset}:{due_date.isoformat()}"
                    )
                    if db.scalar(
                        select(Notification.id).where(
                            Notification.idempotency_key == idempotency_key
                        )
                    ):
                        continue
                    customer = customers.get(invoice.customer_id)
                    if customer is None:
                        logger.warning(
                            "Skipping invoice reminder without customer "
                            "(invoice_id=%s)",
                            invoice.id,
                        )
                        continue
                    notification = NotificationDeliveryService.enqueue(
                        db,
                        customer_id=invoice.customer_id,
                        notification_type=rule.notification_type,
                        title=(
                            f"Invoice {invoice.invoice_number} is due soon"
                            if rule.notification_type == "invoice_due"
                            else f"Invoice {invoice.invoice_number} is overdue"
                        ),
                        values={
                            "customer_name": customer.name,
                            "invoice_number": invoice.invoice_number,
                            "invoice_date": invoice.issue_date.isoformat(),
                            "due_date": invoice.due_date.isoformat(),
                            "invoice_amount": _money(
                                invoice.total_amount, invoice.currency
                            ),
                            "remaining_balance": _money(
                                invoice.outstanding, invoice.currency
                            ),
                            "payment_status": invoice.status,
                            "invoice_url": (
                                f"{settings.FRONTEND_URL.rstrip('/')}/invoices/{invoice.id}"
                            ),
                        },
                        recipient_email=customer.email,
                        related_entity_type="invoice",
                        related_entity_id=invoice.id,
                        idempotency_key=idempotency_key,
                        settings=settings,
                    )
                    if notification is not None:
                        result["invoice_reminders"] += 1
                        failed_delivery = db.scalar(
                            select(NotificationDelivery.id).where(
                                NotificationDelivery.notification_id
                                == notification.id,
                                NotificationDelivery.channel == "email",
                                NotificationDelivery.delivery_status == "failed",
                            )
                        )
                        if failed_delivery is not None:
                            result["failed"] += 1
                if len(invoices) < batch_size:
                    break

        elif rule.notification_type == "subscription_renewal":
            renewal_date = as_of + dt.timedelta(days=rule.days_offset)
            for subscription in subscriptions.all_subscriptions():
                if (
                    subscription.status != "active"
                    or subscription.next_billing_date != renewal_date
                    or (
                        subscription.expiry_date is not None
                        and subscription.expiry_date < as_of
                    )
                ):
                    continue
                idempotency_key = (
                    f"subscription-reminder-{rule.days_offset}:"
                    f"{subscription.id}:{renewal_date.isoformat()}"
                )
                if db.scalar(
                    select(Notification.id).where(
                        Notification.idempotency_key == idempotency_key
                    )
                ):
                    continue
                customer = customers.get(subscription.customer_id)
                if customer is None:
                    logger.warning(
                        "Skipping renewal reminder without customer (subscription_id=%s)",
                        subscription.id,
                    )
                    continue
                try:
                    amount = sum(
                        (
                            pricing.price_line(
                                line.product_id,
                                line.quantity,
                                subscription.customer_id,
                            ).line_total
                            for line in subscription.lines
                        ),
                        Decimal("0"),
                    )
                    notification = notify_subscription_renewal(
                        db,
                        customer_id=subscription.customer_id,
                        customer_name=customer.name,
                        customer_email=customer.email,
                        subscription_id=subscription.id,
                        subscription_name=(
                            subscription.lines[0].description
                            if subscription.lines
                            else f"Subscription {subscription.id}"
                        ),
                        renewal_date=renewal_date,
                        amount=amount,
                        currency=settings.DEFAULT_CURRENCY,
                        settings=settings,
                        days_before=rule.days_offset,
                    )
                    if notification is not None:
                        result["subscription_reminders"] += 1
                        failed_delivery = db.scalar(
                            select(NotificationDelivery.id).where(
                                NotificationDelivery.notification_id
                                == notification.id,
                                NotificationDelivery.channel == "email",
                                NotificationDelivery.delivery_status == "failed",
                            )
                        )
                        if failed_delivery is not None:
                            result["failed"] += 1
                except Exception:
                    result["failed"] += 1
                    logger.exception(
                        "Subscription reminder processing failed "
                        "(subscription_id=%s, days_before=%s)",
                        subscription.id,
                        rule.days_offset,
                    )

    retry_result = retry_due_notifications(
        db, settings=settings, batch_size=batch_size
    )
    result["retried"] += retry_result["retried"]
    result["failed"] += retry_result["failed"]
    return result


def retry_due_notifications(
    db: Session, *, settings: Settings, batch_size: int = 200
) -> dict[str, int]:
    result = {"retried": 0, "failed": 0}
    now = dt.datetime.now(dt.timezone.utc)
    retry_ids = list(
        db.scalars(
            select(NotificationDelivery.id)
            .where(
                NotificationDelivery.channel == "email",
                NotificationDelivery.delivery_status == "failed",
                NotificationDelivery.attempt_count < settings.NOTIFICATION_MAX_ATTEMPTS,
                NotificationDelivery.next_retry_at.is_not(None),
                NotificationDelivery.next_retry_at <= now,
            )
            .order_by(NotificationDelivery.next_retry_at)
            .limit(batch_size)
        ).all()
    )
    for delivery_id in retry_ids:
        delivery = NotificationDeliveryService.dispatch_email(db, delivery_id, settings)
        if delivery.delivery_status in {"sent", "delivered"}:
            result["retried"] += 1
        elif delivery.delivery_status == "failed":
            result["failed"] += 1

    return result
