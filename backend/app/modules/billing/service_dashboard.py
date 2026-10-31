"""Dashboard aggregates — single round-trips, no ORM row iteration (doc §6.D)."""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ...core.time import business_date
from .integrations import CustomerProvider, SubscriptionProvider
from .models import Invoice, Payment
from .schemas import (
    DashboardSummary,
    OverdueInvoiceOut,
    RecentPaymentOut,
    RevenueTrendOut,
    TrendPoint,
)


def summary(
    session: Session,
    subscriptions: SubscriptionProvider,
    customers: CustomerProvider,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> DashboardSummary:
    today = business_date()

    revenue_q = sa.select(sa.func.coalesce(sa.func.sum(Payment.amount), 0)).where(
        Payment.status == "posted"
    )
    if date_from:
        revenue_q = revenue_q.where(
            Payment.paid_at >= dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.timezone.utc)
        )
    if date_to:
        revenue_q = revenue_q.where(
            Payment.paid_at <= dt.datetime.combine(date_to, dt.time.max, tzinfo=dt.timezone.utc)
        )
    revenue_received = session.scalar(revenue_q) or Decimal("0")

    outstanding_amount = session.scalar(
        sa.select(
            sa.func.coalesce(sa.func.sum(Invoice.total_amount - Invoice.amount_paid), 0)
        ).where(Invoice.status == "confirmed")
    ) or Decimal("0")

    overdue_row = session.execute(
        sa.select(
            sa.func.count(Invoice.id),
            sa.func.coalesce(
                sa.func.sum(Invoice.total_amount - Invoice.amount_paid), 0
            ),
        ).where(Invoice.status == "confirmed", Invoice.due_date < today)
    ).one()
    overdue_count, overdue_amount = overdue_row[0], overdue_row[1]

    draft_count = session.scalar(
        sa.select(sa.func.count(Invoice.id)).where(Invoice.status == "draft")
    ) or 0

    recent = session.execute(
        sa.select(Payment, Invoice.invoice_number)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Payment.status == "posted")
        .order_by(Payment.paid_at.desc())
        .limit(5)
    ).all()
    recent_payments = [
        RecentPaymentOut(
            id=p.id,
            payment_reference=p.payment_reference,
            invoice_id=p.invoice_id,
            invoice_number=num,
            amount=p.amount,
            method=p.method,
            paid_at=p.paid_at,
        )
        for p, num in recent
    ]

    overdue_invoices = session.execute(
        sa.select(Invoice)
        .where(Invoice.status == "confirmed", Invoice.due_date < today)
        .order_by(Invoice.due_date.asc())
        .limit(5)
    ).scalars().all()
    names = customers.get_many([i.customer_id for i in overdue_invoices])
    top_overdue = [
        OverdueInvoiceOut(
            id=i.id,
            invoice_number=i.invoice_number,
            customer_id=i.customer_id,
            customer_name=names[i.customer_id].name if i.customer_id in names else None,
            due_date=i.due_date,
            total_amount=i.total_amount,
            amount_paid=i.amount_paid,
            outstanding=i.outstanding,
            days_overdue=(today - i.due_date).days,
        )
        for i in overdue_invoices
    ]

    return DashboardSummary(
        active_subscriptions=subscriptions.count_active(),
        revenue_received=revenue_received,
        outstanding_amount=outstanding_amount,
        overdue_count=overdue_count,
        overdue_amount=overdue_amount,
        draft_count=draft_count,
        recent_payments=recent_payments,
        top_overdue=top_overdue,
    )


_SQLITE_FMT = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m"}


def revenue_trend(
    session: Session,
    *,
    interval: str = "month",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> RevenueTrendOut:
    if interval not in _SQLITE_FMT:
        interval = "month"

    sqlite = session.get_bind().dialect.name == "sqlite"

    def bucket(col):
        if sqlite:
            return sa.func.strftime(_SQLITE_FMT[interval], col)
        return sa.func.date_trunc(interval, col)

    invoiced_q = (
        sa.select(bucket(Invoice.issue_date).label("p"), sa.func.sum(Invoice.total_amount))
        .where(Invoice.status.in_(["confirmed", "paid"]))
        .group_by("p")
    )
    collected_q = (
        sa.select(bucket(Payment.paid_at).label("p"), sa.func.sum(Payment.amount))
        .where(Payment.status == "posted")
        .group_by("p")
    )
    if date_from:
        invoiced_q = invoiced_q.where(Invoice.issue_date >= date_from)
        collected_q = collected_q.where(
            Payment.paid_at >= dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.timezone.utc)
        )
    if date_to:
        invoiced_q = invoiced_q.where(Invoice.issue_date <= date_to)
        collected_q = collected_q.where(
            Payment.paid_at <= dt.datetime.combine(date_to, dt.time.max, tzinfo=dt.timezone.utc)
        )

    invoiced = {p: amt for p, amt in session.execute(invoiced_q).all()}
    collected = {p: amt for p, amt in session.execute(collected_q).all()}

    # Outstanding is a point-in-time running balance — seed it with everything
    # invoiced/collected BEFORE the displayed range. Without this baseline a
    # filtered view under-reports outstanding (or even goes negative when a
    # payment inside the range settles an invoice issued before it).
    running = Decimal("0")
    if date_from:
        baseline_start = dt.datetime.combine(
            date_from, dt.time.min, tzinfo=dt.timezone.utc
        )
        base_invoiced = session.scalar(
            sa.select(
                sa.func.coalesce(sa.func.sum(Invoice.total_amount), 0)
            ).where(
                Invoice.status.in_(["confirmed", "paid"]),
                Invoice.issue_date < date_from,
            )
        ) or Decimal("0")
        base_collected = session.scalar(
            sa.select(
                sa.func.coalesce(sa.func.sum(Payment.amount), 0)
            ).where(
                Payment.status == "posted",
                Payment.paid_at < baseline_start,
            )
        ) or Decimal("0")
        running = Decimal(str(base_invoiced)) - Decimal(str(base_collected))

    points: list[TrendPoint] = []
    for period in sorted(set(invoiced) | set(collected)):
        inv = invoiced.get(period, Decimal("0")) or Decimal("0")
        col = collected.get(period, Decimal("0")) or Decimal("0")
        running += inv - col
        points.append(
            TrendPoint(period=str(period), invoiced=inv, collected=col, outstanding=running)
        )

    return RevenueTrendOut(interval=interval, points=points)
