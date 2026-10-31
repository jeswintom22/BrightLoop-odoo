"""Customer portal — /api/v1/portal/* — strictly scoped to the caller's own
customer record (role=customer). P4 invoices/payments join through
customers.id, so changing an id in the URL can never leak another tenant."""

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.pagination import Page
from ...deps import CurrentUser, get_db, require_roles
from ..billing.models import Invoice, Payment
from ..billing.schemas import InvoiceDetail, InvoiceSummary, PaymentOut
from ..subscriptions.models import Subscription
from .models import Customer
from .schemas import CustomerOut

router = APIRouter(prefix="/portal", tags=["portal"])

CUSTOMER = Depends(require_roles("customer"))


def _my_customer(session: Session, user: CurrentUser) -> Customer:
    customer = session.scalar(
        sa.select(Customer).where(Customer.user_id == user.id)
    )
    if customer is None:
        raise AppError(
            "NO_CUSTOMER", "No customer profile is linked to this account", 403
        )
    return customer


@router.get("/me", response_model=CustomerOut)
def portal_me(session: Session = Depends(get_db), user: CurrentUser = CUSTOMER):
    return CustomerOut.model_validate(_my_customer(session, user))


@router.get("/subscriptions")
def portal_subscriptions(
    session: Session = Depends(get_db), user: CurrentUser = CUSTOMER
):
    customer = _my_customer(session, user)
    subs = session.scalars(
        sa.select(Subscription)
        .where(Subscription.customer_id == customer.id)
        .order_by(Subscription.created_at.desc())
    ).all()
    return [
        {
            "id": str(s.id),
            "subscription_number": s.subscription_number,
            "status": s.status,
            "billing_frequency": s.billing_frequency,
            "start_date": s.start_date.isoformat() if s.start_date else None,
            "expiry_date": s.expiry_date.isoformat() if s.expiry_date else None,
            "next_billing_date": (
                s.next_billing_date.isoformat() if s.next_billing_date else None
            ),
        }
        for s in subs
    ]


@router.get("/invoices", response_model=Page[InvoiceSummary])
def portal_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    session: Session = Depends(get_db),
    user: CurrentUser = CUSTOMER,
):
    customer = _my_customer(session, user)
    q = sa.select(Invoice).where(Invoice.customer_id == customer.id)
    count_q = (
        sa.select(sa.func.count())
        .select_from(Invoice)
        .where(Invoice.customer_id == customer.id)
    )
    if status:
        q = q.where(Invoice.status == status)
        count_q = count_q.where(Invoice.status == status)
    total = session.scalar(count_q) or 0
    rows = session.scalars(
        q.order_by(Invoice.issue_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        items=[InvoiceSummary.model_validate(i) for i in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def portal_invoice_detail(
    invoice_id: uuid.UUID,
    session: Session = Depends(get_db),
    user: CurrentUser = CUSTOMER,
):
    customer = _my_customer(session, user)
    invoice = session.scalar(
        sa.select(Invoice).where(
            Invoice.id == invoice_id, Invoice.customer_id == customer.id
        )
    )
    if invoice is None:
        # same 404 whether it doesn't exist or belongs to someone else
        raise AppError("NOT_FOUND", "Invoice not found", 404)
    return InvoiceDetail.model_validate(invoice)


@router.get("/payments", response_model=Page[PaymentOut])
def portal_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    user: CurrentUser = CUSTOMER,
):
    customer = _my_customer(session, user)
    base = (
        sa.select(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.customer_id == customer.id)
    )
    count_q = (
        sa.select(sa.func.count())
        .select_from(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.customer_id == customer.id)
    )
    total = session.scalar(count_q) or 0
    rows = session.scalars(
        base.order_by(Payment.paid_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(
        items=[PaymentOut.model_validate(p) for p in rows],
        total=total, page=page, page_size=page_size,
    )
