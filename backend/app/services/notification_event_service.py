import datetime as dt
import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.billing.integrations import CustomerProvider
from app.modules.billing.models import BillingRun, Invoice, Payment
from app.models.notification import Notification
from app.services.notification_delivery_service import NotificationDeliveryService

logger = logging.getLogger("brightloop.notifications.events")


def _money(amount: Decimal, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _production_stubs(settings: Settings, *providers: object) -> bool:
    return settings.ENVIRONMENT.lower() in {"prod", "production"} and any(
        getattr(provider, "is_stub_provider", False) for provider in providers
    )


def notify_invoice_generated(
    db: Session,
    *,
    invoice: Invoice,
    customers: CustomerProvider,
    settings: Settings,
    event: str = "generated",
) -> Notification | None:
    if _production_stubs(settings, customers):
        logger.error("Invoice notification suppressed because customer provider is a stub")
        return None
    customer = customers.get(invoice.customer_id)
    if customer is None:
        logger.error(
            "Invoice notification suppressed because customer is unavailable "
            "(invoice_id=%s)",
            invoice.id,
        )
        return None
    title = (
        f"Invoice {invoice.invoice_number} is ready"
        if event == "generated"
        else f"Invoice {invoice.invoice_number} was updated"
    )
    return NotificationDeliveryService.enqueue(
        db,
        customer_id=invoice.customer_id,
        notification_type="invoice_generated",
        title=title,
        values={
            "customer_name": customer.name,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.issue_date.isoformat(),
            "due_date": invoice.due_date.isoformat(),
            "invoice_amount": _money(invoice.total_amount, invoice.currency),
            "remaining_balance": _money(invoice.outstanding, invoice.currency),
            "payment_status": invoice.status,
            "invoice_url": f"{settings.FRONTEND_URL.rstrip('/')}/invoices/{invoice.id}",
        },
        recipient_email=customer.email,
        related_entity_type="invoice",
        related_entity_id=invoice.id,
        idempotency_key=(
            f"invoice-{event}:{invoice.id}:"
            f"{invoice.updated_at.isoformat() if event == 'updated' else 'initial'}"
        ),
        settings=settings,
    )


def notify_payment_confirmed(
    db: Session,
    *,
    payment: Payment,
    customers: CustomerProvider,
    settings: Settings,
) -> Notification | None:
    if _production_stubs(settings, customers):
        logger.error("Payment notification suppressed because customer provider is a stub")
        return None
    invoice = db.get(Invoice, payment.invoice_id)
    if invoice is None:
        logger.error(
            "Payment notification suppressed because invoice is unavailable "
            "(payment_id=%s)",
            payment.id,
        )
        return None
    customer = customers.get(invoice.customer_id)
    if customer is None:
        logger.error(
            "Payment notification suppressed because customer is unavailable "
            "(payment_id=%s)",
            payment.id,
        )
        return None
    return NotificationDeliveryService.enqueue(
        db,
        customer_id=invoice.customer_id,
        notification_type="payment_confirmation",
        title=f"Payment received for invoice {invoice.invoice_number}",
        values={
            "customer_name": customer.name,
            "transaction_id": payment.payment_reference,
            "payment_method": payment.method.replace("_", " "),
            "payment_date": payment.paid_at.isoformat(),
            "invoice_number": invoice.invoice_number,
            "invoice_amount": _money(payment.amount, invoice.currency),
            "remaining_balance": _money(invoice.outstanding, invoice.currency),
            "invoice_url": f"{settings.FRONTEND_URL.rstrip('/')}/invoices/{invoice.id}",
        },
        recipient_email=customer.email,
        related_entity_type="payment",
        related_entity_id=payment.id,
        idempotency_key=f"payment-confirmation:{payment.id}",
        settings=settings,
        essential=True,
    )


def notify_subscription_renewal(
    db: Session,
    *,
    customer_id: uuid.UUID,
    customer_name: str,
    customer_email: str,
    subscription_id: uuid.UUID,
    subscription_name: str,
    renewal_date: dt.date,
    amount: Decimal,
    currency: str,
    settings: Settings,
    confirmation: bool = False,
    days_before: int | None = None,
    customer_provider_is_stub: bool = False,
) -> Notification | None:
    if (
        settings.ENVIRONMENT.lower() in {"prod", "production"}
        and customer_provider_is_stub
    ):
        logger.error(
            "Subscription notification suppressed because customer provider is a stub"
        )
        return None
    notification_type = "subscription_renewal"
    values = {
        "customer_name": customer_name,
        "subscription_name": subscription_name,
        "renewal_date": renewal_date.isoformat(),
        "renewal_status": "has been renewed" if confirmation else "will renew soon",
        "invoice_amount": _money(amount, currency),
        "payment_instructions": settings.PAYMENT_INSTRUCTIONS,
        "account_url": settings.FRONTEND_URL.rstrip("/"),
        "transaction_id": f"subscription-renewal-{subscription_id}",
        "payment_date": renewal_date.isoformat(),
        "payment_method": "account renewal",
        "invoice_number": subscription_name,
        "remaining_balance": _money(Decimal("0"), currency),
        "invoice_url": settings.FRONTEND_URL.rstrip("/"),
    }
    event = (
        "confirmed"
        if confirmation
        else f"reminder-{days_before}"
    )
    return NotificationDeliveryService.enqueue(
        db,
        customer_id=customer_id,
        notification_type=notification_type,
        title=(
            f"Subscription {subscription_name} renewed"
            if confirmation
            else f"Subscription {subscription_name} renews soon"
        ),
        values=values,
        recipient_email=customer_email,
        related_entity_type="subscription",
        related_entity_id=subscription_id,
        idempotency_key=(
            f"subscription-{event}:{subscription_id}:"
            f"{renewal_date.isoformat()}"
        ),
        settings=settings,
        essential=confirmation,
    )


def notify_billing_run_invoices(
    session_factory,
    *,
    run: BillingRun,
    customers: CustomerProvider,
    settings: Settings,
) -> int:
    count = 0
    with session_factory() as db:
        invoices = list(
            db.scalars(
                select(Invoice).where(Invoice.billing_run_id == run.id)
            ).all()
        )
        for invoice in invoices:
            notification = notify_invoice_generated(
                db, invoice=invoice, customers=customers, settings=settings
            )
            if notification is not None:
                count += 1
    return count
