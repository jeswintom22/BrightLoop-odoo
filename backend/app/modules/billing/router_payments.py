import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ...core.config import Settings, get_settings
from ...core.errors import AppError
from ...core.pagination import Page
from ...deps import (
    CurrentUser,
    get_customer_provider,
    get_db,
    get_subscription_provider,
    require_roles,
)
from ...services.notification_delivery_service import NotificationDeliveryService
from ...services.notification_event_service import (
    notify_payment_confirmed,
    notify_subscription_renewal,
)
from . import repository as repo
from .integrations import CustomerProvider, SubscriptionProvider
from .models import Invoice
from .schemas import (
    PaymentCreateRequest,
    PaymentOut,
    PaymentVoidRequest,
)
from .service_payments import PaymentService

router = APIRouter(tags=["payments"])

READ = Depends(require_roles("admin", "staff"))
WRITE = Depends(require_roles("admin", "staff"))

_payments = PaymentService()


@router.post("/payments", response_model=PaymentOut)
def record_payment(
    body: PaymentCreateRequest,
    response: Response,
    session: Session = Depends(get_db),
    customers: CustomerProvider = Depends(get_customer_provider),
    subscriptions: SubscriptionProvider = Depends(get_subscription_provider),
    settings: Settings = Depends(get_settings),
    user: CurrentUser = WRITE,
):
    payment, created = _payments.record_payment(
        session,
        invoice_id=body.invoice_id,
        amount=body.amount,
        method=body.method,
        paid_at=body.paid_at,
        notes=body.notes,
        idempotency_key=body.idempotency_key,
        actor_id=user.id,
    )
    session.commit()
    invoice = session.get(Invoice, payment.invoice_id)
    if invoice is not None:
        notify_payment_confirmed(
            session, payment=payment, customers=customers, settings=settings
        )
        if invoice.outstanding <= 0:
            NotificationDeliveryService.cancel_invoice_reminders(session, invoice.id)
            if invoice.subscription_id is not None:
                subscription = subscriptions.get_subscription_view(
                    invoice.subscription_id
                )
                customer = customers.get(invoice.customer_id)
                if subscription is not None and customer is not None:
                    notify_subscription_renewal(
                        session,
                        customer_id=invoice.customer_id,
                        customer_name=customer.name,
                        customer_email=customer.email,
                        subscription_id=subscription.id,
                        subscription_name=(
                            subscription.lines[0].description
                            if subscription.lines
                            else f"Subscription {subscription.id}"
                        ),
                        renewal_date=invoice.period_end,
                        amount=invoice.total_amount,
                        currency=invoice.currency,
                        settings=settings,
                        confirmation=True,
                        customer_provider_is_stub=getattr(
                            customers, "is_stub_provider", False
                        ),
                    )
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return payment


@router.get("/payments", response_model=Page[PaymentOut])
def list_payments(
    invoice_id: uuid.UUID | None = None,
    method: str | None = None,
    status_: str | None = Query(None, alias="status"),
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    sort: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    items, total = repo.list_payments(
        session,
        invoice_id=invoice_id,
        method=method,
        status=status_,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: uuid.UUID,
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    payment = repo.get_payment(session, payment_id)
    if payment is None:
        raise AppError("PAYMENT_NOT_FOUND", "Payment not found", 404)
    return payment


@router.post("/payments/{payment_id}/void", response_model=PaymentOut)
def void_payment(
    payment_id: uuid.UUID,
    body: PaymentVoidRequest,
    session: Session = Depends(get_db),
    user: CurrentUser = WRITE,
):
    payment = _payments.void_payment(
        session, payment_id, reason=body.reason, actor_id=user.id
    )
    session.commit()
    return payment
