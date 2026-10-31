"""Revenue growth analytics + breakdowns.

Definitions (fixed):
- ``invoiced``  = Σ invoices.total_amount where status ∈ (confirmed, paid),
                  bucketed by issue_date. Drafts and cancelled are excluded.
- ``collected`` = Σ payments.amount where status = 'posted',
                  bucketed by paid_at. Voided payments are excluded.
- These are CASH-IN-MOTION metrics, deliberately distinct from MRR/ARR
  (recurring contract value) — never conflate them.
- Growth % = (current − previous) / previous × 100; ``None`` when the
  previous period is zero (no meaningful percentage).
- Buckets: day | week | month | year. Portable across SQLite and Postgres.
"""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ...billing.models import Invoice, InvoiceLine, Payment
from ...subscriptions.models import Subscription
from ....models.product import Product
from ....models.subscription_plan import SubscriptionPlan

CENTS = Decimal("0.01")

_SQLITE_FMT = {
    "day": "%Y-%m-%d",
    "week": "%Y-W%W",
    "month": "%Y-%m",
    "year": "%Y",
}
INTERVALS = tuple(_SQLITE_FMT)


def _day_bounds(d: dt.date) -> tuple[dt.datetime, dt.datetime]:
    return (
        dt.datetime.combine(d, dt.time.min, tzinfo=dt.timezone.utc),
        dt.datetime.combine(d, dt.time.max, tzinfo=dt.timezone.utc),
    )


def _bucket_expr(session: Session, interval: str, col):
    if session.get_bind().dialect.name == "sqlite":
        return sa.func.strftime(_SQLITE_FMT[interval], col)
    return sa.func.date_trunc(interval, col)


def revenue_trends(
    session: Session,
    *,
    interval: str,
    date_from: dt.date,
    date_to: dt.date,
) -> dict:
    """Per-bucket invoiced/collected + period-over-period comparison.

    The previous period is the same-length window ending the day before
    `date_from`; growth percentages are computed on totals, not per bucket.
    """
    if interval not in _SQLITE_FMT:
        interval = "month"

    invoiced_q = (
        sa.select(
            _bucket_expr(session, interval, Invoice.issue_date).label("p"),
            sa.func.sum(Invoice.total_amount),
        )
        .where(
            Invoice.status.in_(["confirmed", "paid"]),
            Invoice.issue_date >= date_from,
            Invoice.issue_date <= date_to,
        )
        .group_by("p")
    )
    lo, hi = _day_bounds(date_from)[0], _day_bounds(date_to)[1]
    collected_q = (
        sa.select(
            _bucket_expr(session, interval, Payment.paid_at).label("p"),
            sa.func.sum(Payment.amount),
        )
        .where(
            Payment.status == "posted",
            Payment.paid_at >= lo,
            Payment.paid_at <= hi,
        )
        .group_by("p")
    )

    invoiced = {str(p): Decimal(str(a)) for p, a in session.execute(invoiced_q).all()}
    collected = {str(p): Decimal(str(a)) for p, a in session.execute(collected_q).all()}

    q = lambda v: v.quantize(CENTS)
    points = [
        {
            "period": p,
            "invoiced": q(invoiced.get(p, Decimal("0"))),
            "collected": q(collected.get(p, Decimal("0"))),
        }
        for p in sorted(set(invoiced) | set(collected))
    ]

    window = (date_to - date_from).days + 1
    prev_to = date_from - dt.timedelta(days=1)
    prev_from = prev_to - dt.timedelta(days=window - 1)

    cur_inv = sum(invoiced.values(), Decimal("0"))
    cur_col = sum(collected.values(), Decimal("0"))
    p_lo, p_hi = _day_bounds(prev_from)[0], _day_bounds(prev_to)[1]

    prev_inv = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Invoice.total_amount), 0)).where(
            Invoice.status.in_(["confirmed", "paid"]),
            Invoice.issue_date >= prev_from,
            Invoice.issue_date <= prev_to,
        )
    ) or Decimal("0")
    prev_col = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Payment.amount), 0)).where(
            Payment.status == "posted",
            Payment.paid_at >= p_lo,
            Payment.paid_at <= p_hi,
        )
    ) or Decimal("0")

    def growth(cur: Decimal, prev: Decimal) -> Decimal | None:
        if prev == 0:
            return None
        return ((cur - prev) / prev * Decimal("100")).quantize(Decimal("0.01"))

    return {
        "interval": interval,
        "range": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "previous_range": {"from": prev_from.isoformat(), "to": prev_to.isoformat()},
        "totals": {"invoiced": q(cur_inv), "collected": q(cur_col)},
        "previous_totals": {"invoiced": q(Decimal(str(prev_inv))), "collected": q(Decimal(str(prev_col)))},
        "growth_pct": {
            "invoiced": growth(cur_inv, Decimal(str(prev_inv))),
            "collected": growth(cur_col, Decimal(str(prev_col))),
        },
        "points": points,
    }


_BREAKDOWN_STATUSES = ["confirmed", "paid"]


def breakdown(
    session: Session,
    *,
    by: str,
    date_from: dt.date,
    date_to: dt.date,
    limit: int = 20,
) -> list[dict]:
    """Revenue breakdown. `by` ∈ plan|product|customer|period|payment_method.

    Amount semantics per dimension:
    - plan / customer / period → invoiced total (confirmed+paid invoices).
    - product → Σ invoice_lines.line_total on those invoices.
    - payment_method → cash actually collected (posted payments).
    """
    if by == "product":
        stmt = (
            sa.select(
                sa.func.coalesce(Product.name, InvoiceLine.description).label("k"),
                sa.func.sum(InvoiceLine.line_total).label("amt"),
            )
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
            .outerjoin(Product, InvoiceLine.product_id == Product.id)
            .where(
                Invoice.status.in_(_BREAKDOWN_STATUSES),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
            )
            .group_by("k")
        )
    elif by == "plan":
        stmt = (
            sa.select(
                sa.func.coalesce(SubscriptionPlan.name, sa.literal("No plan")).label("k"),
                sa.func.sum(Invoice.total_amount).label("amt"),
            )
            .outerjoin(Subscription, Invoice.subscription_id == Subscription.id)
            .outerjoin(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
            .where(
                Invoice.status.in_(_BREAKDOWN_STATUSES),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
            )
            .group_by("k")
        )
    elif by == "customer":
        customers = sa.table(
            "customers", sa.column("id", sa.Uuid), sa.column("name")
        )
        stmt = (
            sa.select(
                sa.func.coalesce(customers.c.name, Invoice.customer_id.cast(sa.String)).label("k"),
                sa.func.sum(Invoice.total_amount).label("amt"),
            )
            .outerjoin(customers, Invoice.customer_id == customers.c.id)
            .where(
                Invoice.status.in_(_BREAKDOWN_STATUSES),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
            )
            .group_by("k")
        )
    elif by == "period":
        stmt = (
            sa.select(
                _bucket_expr(session, "month", Invoice.period_start).label("k"),
                sa.func.sum(Invoice.total_amount).label("amt"),
            )
            .where(
                Invoice.status.in_(_BREAKDOWN_STATUSES),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
            )
            .group_by("k")
        )
    elif by == "payment_method":
        lo, hi = _day_bounds(date_from)[0], _day_bounds(date_to)[1]
        stmt = (
            sa.select(
                Payment.method.label("k"),
                sa.func.sum(Payment.amount).label("amt"),
            )
            .where(
                Payment.status == "posted",
                Payment.paid_at >= lo,
                Payment.paid_at <= hi,
            )
            .group_by(Payment.method)
        )
    else:
        raise ValueError(f"unknown breakdown dimension: {by}")

    rows = session.execute(stmt.order_by(sa.desc("amt")).limit(limit)).all()
    total = sum((Decimal(str(a)) for _, a in rows), Decimal("0"))
    q = lambda v: v.quantize(CENTS)
    return [
        {
            "key": str(k),
            "amount": q(Decimal(str(a))),
            "share_pct": (
                (Decimal(str(a)) / total * Decimal("100")).quantize(Decimal("0.01"))
                if total
                else Decimal("0")
            ),
        }
        for k, a in rows
    ]
