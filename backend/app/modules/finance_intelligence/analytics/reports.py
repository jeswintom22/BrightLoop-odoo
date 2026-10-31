"""Financial performance report assembly — deterministic aggregates only."""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ....core.time import business_date
from ...billing.models import Invoice, Payment
from ...subscriptions.models import Subscription
from . import mrr_arr, revenue

CENTS = Decimal("0.01")


def _day_bounds(d: dt.date):
    return (
        dt.datetime.combine(d, dt.time.min, tzinfo=dt.timezone.utc),
        dt.datetime.combine(d, dt.time.max, tzinfo=dt.timezone.utc),
    )


def _totals(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    lo, hi = _day_bounds(date_from)[0], _day_bounds(date_to)[1]

    inv_row = session.execute(
        sa.select(
            sa.func.count(Invoice.id),
            sa.func.coalesce(sa.func.sum(Invoice.total_amount), 0),
        ).where(
            Invoice.status.in_(["confirmed", "paid"]),
            Invoice.issue_date >= date_from,
            Invoice.issue_date <= date_to,
        )
    ).one()

    collected = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Payment.amount), 0)).where(
            Payment.status == "posted",
            Payment.paid_at >= lo,
            Payment.paid_at <= hi,
        )
    ) or Decimal("0")

    today = business_date()
    outstanding = session.scalar(
        sa.select(
            sa.func.coalesce(
                sa.func.sum(Invoice.total_amount - Invoice.amount_paid), 0
            )
        ).where(Invoice.status == "confirmed")
    ) or Decimal("0")

    overdue_row = session.execute(
        sa.select(
            sa.func.count(Invoice.id),
            sa.func.coalesce(
                sa.func.sum(Invoice.total_amount - Invoice.amount_paid), 0
            ),
        ).where(
            Invoice.status == "confirmed",
            Invoice.due_date < today,
        )
    ).one()

    return {
        "invoice_count": int(inv_row[0]),
        "invoiced": Decimal(str(inv_row[1])),
        "collected": Decimal(str(collected)),
        "outstanding": Decimal(str(outstanding)),
        "overdue_count": int(overdue_row[0]),
        "overdue_amount": Decimal(str(overdue_row[1])),
    }


def performance_report(
    session: Session, *, date_from: dt.date, date_to: dt.date
) -> dict:
    """Revenue + collection + outstanding performance over a period, with a
    same-length previous-period comparison."""
    window = (date_to - date_from).days + 1
    prev_to = date_from - dt.timedelta(days=1)
    prev_from = prev_to - dt.timedelta(days=window - 1)

    cur = _totals(session, date_from, date_to)
    prev = _totals(session, prev_from, prev_to)

    def growth(cur_v: Decimal, prev_v: Decimal) -> Decimal | None:
        if prev_v == 0:
            return None
        return ((cur_v - prev_v) / prev_v * Decimal("100")).quantize(Decimal("0.01"))

    collection_rate = (
        (cur["collected"] / cur["invoiced"]).quantize(Decimal("0.0001"))
        if cur["invoiced"] > 0
        else None
    )

    snap = mrr_arr.mrr_snapshot(session, date_to)
    q = lambda v: v.quantize(CENTS)

    return {
        "range": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "previous_range": {"from": prev_from.isoformat(), "to": prev_to.isoformat()},
        "current": {k: (q(v) if isinstance(v, Decimal) else v) for k, v in cur.items()},
        "previous": {k: (q(v) if isinstance(v, Decimal) else v) for k, v in prev.items()},
        "growth_pct": {
            "invoiced": growth(cur["invoiced"], prev["invoiced"]),
            "collected": growth(cur["collected"], prev["collected"]),
        },
        "collection_rate": collection_rate,
        "mrr": snap["mrr"],
        "arr": snap["arr"],
        "active_subscriptions_in_mrr": snap["subscription_count"],
        "plan_revenue": revenue.breakdown(
            session, by="plan", date_from=date_from, date_to=date_to
        ),
    }
