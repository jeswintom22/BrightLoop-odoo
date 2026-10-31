"""Deterministic collection forecast — NOT a trained ML model.

Two clearly-separated figures:

- ``expected_billings``   — invoices the billing engine is expected to issue:
  active subscriptions with next_billing_date inside the horizon, valued at
  Σ items(quantity × unit_price × (1 + tax_rate/100)) per billing cycle.
- ``expected_collections`` — cash expected on *existing* receivables:
  outstanding balance on confirmed invoices due inside the horizon,
  weighted by the realized collection rate over the trailing 90 days:
      rate = collected(90d) / invoiced(90d), clamped to [0, 1]
  plus the full outstanding of already-overdue invoices times the same rate.

Every input is a database aggregate; the heuristic is transparent so a human
can audit each number. No ML claims are made anywhere.
"""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ....core.time import business_date
from ...billing.models import Invoice, Payment
from ...subscriptions.models import Subscription
from ...auth.models import Customer

CENTS = Decimal("0.01")
RATE_WINDOW_DAYS = 90


def _day_bounds(d: dt.date):
    return (
        dt.datetime.combine(d, dt.time.min, tzinfo=dt.timezone.utc),
        dt.datetime.combine(d, dt.time.max, tzinfo=dt.timezone.utc),
    )


def _expected_cycle_amount(sub: Subscription) -> Decimal:
    total = Decimal("0")
    for item in sub.items:
        qty = Decimal(str(item.quantity or 0))
        unit = Decimal(str(item.unit_price or 0))
        tax = Decimal(str(item.tax_rate or 0))
        total += (qty * unit * (1 + tax / Decimal("100")))
    return total.quantize(CENTS)


def collection_rate(session: Session, *, as_of: dt.date | None = None) -> Decimal:
    """Realized cash-collection rate over the trailing 90 days."""
    as_of = as_of or business_date()
    start = as_of - dt.timedelta(days=RATE_WINDOW_DAYS)
    invoiced = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Invoice.total_amount), 0)).where(
            Invoice.status.in_(["confirmed", "paid"]),
            Invoice.issue_date >= start,
            Invoice.issue_date <= as_of,
        )
    ) or Decimal("0")
    invoiced = Decimal(str(invoiced))
    if invoiced <= 0:
        return Decimal("0")
    lo, hi = _day_bounds(start)[0], _day_bounds(as_of)[1]
    collected = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Payment.amount), 0)).where(
            Payment.status == "posted",
            Payment.paid_at >= lo,
            Payment.paid_at <= hi,
        )
    ) or Decimal("0")
    rate = Decimal(str(collected)) / invoiced
    return max(Decimal("0"), min(rate, Decimal("1")))


def forecast(session: Session, *, horizon_days: int = 30) -> dict:
    today = business_date()
    horizon_end = today + dt.timedelta(days=horizon_days)
    rate = collection_rate(session, as_of=today)

    # --- expected billings: active subscriptions due to bill in the horizon --
    subs = session.execute(
        sa.select(Subscription).where(
            Subscription.status == "active",
            Subscription.next_billing_date.is_not(None),
            Subscription.next_billing_date >= today,
            Subscription.next_billing_date <= horizon_end,
            sa.or_(
                Subscription.expiry_date.is_(None),
                Subscription.expiry_date >= Subscription.next_billing_date,
            ),
        )
    ).scalars().all()

    expected_billings = Decimal("0")
    upcoming: list[dict] = []
    for sub in subs:
        amount = _expected_cycle_amount(sub)
        expected_billings += amount
        upcoming.append(
            {
                "subscription_id": str(sub.id),
                "subscription_number": sub.subscription_number,
                "customer_id": str(sub.customer_id),
                "next_billing_date": sub.next_billing_date.isoformat(),
                "billing_frequency": sub.billing_frequency,
                "expected_amount": amount,
            }
        )
    upcoming.sort(key=lambda r: r["next_billing_date"])

    # --- expected collections on existing receivables ------------------------
    outstanding_col = Invoice.total_amount - Invoice.amount_paid
    due_rows = session.execute(
        sa.select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.customer_id,
            Customer.name,
            Invoice.due_date,
            outstanding_col.label("outstanding"),
        )
        .outerjoin(Customer, Invoice.customer_id == Customer.id)
        .where(
            Invoice.status == "confirmed",
            Invoice.due_date <= horizon_end,
            outstanding_col > 0,
        )
        .order_by(Invoice.due_date)
    ).all()

    outstanding_total = sum((Decimal(str(r.outstanding)) for r in due_rows), Decimal("0"))
    expected_collections = (outstanding_total * rate).quantize(CENTS)

    return {
        "as_of": today.isoformat(),
        "horizon_days": horizon_days,
        "horizon_end": horizon_end.isoformat(),
        "collection_rate": rate.quantize(Decimal("0.0001")),
        "collection_rate_window_days": RATE_WINDOW_DAYS,
        "expected_billings": expected_billings.quantize(CENTS),
        "expected_billings_count": len(upcoming),
        "outstanding_due": outstanding_total.quantize(CENTS),
        "expected_collections": expected_collections,
        "expected_total_cash_in": (expected_collections + expected_billings * rate).quantize(CENTS),
        "upcoming_billings": upcoming,
        "due_receivables": [
            {
                "invoice_id": str(r.id),
                "invoice_number": r.invoice_number,
                "customer_id": str(r.customer_id),
                "customer_name": r.name,
                "due_date": r.due_date.isoformat(),
                "outstanding": Decimal(str(r.outstanding)).quantize(CENTS),
                "days_overdue": max((today - r.due_date).days, 0),
            }
            for r in due_rows
        ],
    }
