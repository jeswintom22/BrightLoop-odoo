"""Filtered/paginated queries for the billing tables."""

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from ...core.pagination import apply_sort, paginate
from ...core.time import business_date
from .models import Invoice, Payment


def get_invoice(session: Session, invoice_id: uuid.UUID) -> Invoice | None:
    return session.execute(
        sa.select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.lines), selectinload(Invoice.payments))
    ).scalar_one_or_none()


def get_invoice_for_update(session: Session, invoice_id: uuid.UUID) -> Invoice | None:
    return session.execute(
        sa.select(Invoice).where(Invoice.id == invoice_id).with_for_update()
    ).scalar_one_or_none()


def get_invoice_by_period(
    session: Session,
    subscription_id: uuid.UUID,
    period_start: dt.date,
    period_end: dt.date,
) -> Invoice | None:
    return session.execute(
        sa.select(Invoice).where(
            Invoice.subscription_id == subscription_id,
            Invoice.period_start == period_start,
            Invoice.period_end == period_end,
        )
    ).scalar_one_or_none()


def list_invoices(
    session: Session,
    *,
    status: str | None = None,
    customer_id: uuid.UUID | None = None,
    subscription_id: uuid.UUID | None = None,
    overdue: bool = False,
    q: str | None = None,
    issue_from: dt.date | None = None,
    issue_to: dt.date | None = None,
    due_to: dt.date | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Invoice], int]:
    stmt = sa.select(Invoice)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if subscription_id:
        stmt = stmt.where(Invoice.subscription_id == subscription_id)
    if overdue:
        stmt = stmt.where(
            Invoice.status == "confirmed", Invoice.due_date < business_date()
        )
    if q:
        stmt = stmt.where(Invoice.invoice_number.ilike(f"%{q}%"))
    if issue_from:
        stmt = stmt.where(Invoice.issue_date >= issue_from)
    if issue_to:
        stmt = stmt.where(Invoice.issue_date <= issue_to)
    if due_to:
        stmt = stmt.where(Invoice.due_date <= due_to)
    stmt = apply_sort(stmt, Invoice, sort, "-created_at")
    return paginate(session, stmt, page, page_size)


def get_payment(session: Session, payment_id: uuid.UUID) -> Payment | None:
    return session.get(Payment, payment_id)


def get_payment_by_key(session: Session, idempotency_key: str) -> Payment | None:
    return session.execute(
        sa.select(Payment).where(Payment.idempotency_key == idempotency_key)
    ).scalar_one_or_none()


def list_payments(
    session: Session,
    *,
    invoice_id: uuid.UUID | None = None,
    method: str | None = None,
    status: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Payment], int]:
    stmt = sa.select(Payment)
    if invoice_id:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    if method:
        stmt = stmt.where(Payment.method == method)
    if status:
        stmt = stmt.where(Payment.status == status)
    if date_from:
        stmt = stmt.where(Payment.paid_at >= dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.timezone.utc))
    if date_to:
        stmt = stmt.where(Payment.paid_at <= dt.datetime.combine(date_to, dt.time.max, tzinfo=dt.timezone.utc))
    stmt = apply_sort(stmt, Payment, sort, "-paid_at")
    return paginate(session, stmt, page, page_size)
