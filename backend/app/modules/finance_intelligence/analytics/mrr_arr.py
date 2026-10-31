"""MRR / ARR — normalized recurring revenue from subscription records.

Calculation rules (fixed, documented — see docs/PHASE2_PERSON4_ARCHITECTURE.md):

- Eligible subscriptions: ``subscriptions.status == 'active'`` only.
  paused / closed / draft / confirmed contribute nothing while inactive.
- Recurring amount per subscription = Σ items(quantity × unit_price).
  Pre-tax: GST/VAT is a pass-through liability, not revenue. One-time
  charges never enter MRR — only the recurring subscription lines are read.
  (No discount field exists on subscription items today; documented limit.)
- Frequency normalization to a monthly basis:
      daily   → × 365 / 12
      weekly  → × 52  / 12
      monthly → × 1
      yearly  → ÷ 12
- ARR = MRR × 12.
- MRR must never be derived from invoice totals or cash collected — those
  are separate metrics (see analytics/revenue.py).
- Historical MRR ("as of" a past date): subscriptions whose start_date ≤
  as_of AND (expiry_date IS NULL OR expiry_date > as_of), restricted to subs
  active *today*. Subscriptions carry no status-change history, so a sub that
  was paused mid-period still counts for past dates — documented limitation.

All money is ``Decimal`` end-to-end; results quantize to paise (0.01).
"""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ...subscriptions.models import Subscription, SubscriptionItem
from ....models.subscription_plan import SubscriptionPlan

CENTS = Decimal("0.01")

MONTHS_PER_YEAR = Decimal("12")
_DAILY = Decimal("365") / MONTHS_PER_YEAR
_WEEKLY = Decimal("52") / MONTHS_PER_YEAR

FREQUENCY_FACTORS: dict[str, Decimal] = {
    "daily": _DAILY,
    "weekly": _WEEKLY,
    "monthly": Decimal("1"),
    "yearly": Decimal("1") / MONTHS_PER_YEAR,
}


def monthly_factor(frequency: str) -> Decimal:
    """Multiplier converting one billing-cycle charge to a monthly amount."""
    return FREQUENCY_FACTORS.get((frequency or "monthly").lower(), Decimal("1"))


def _recurring_amount(items: list[SubscriptionItem]) -> Decimal:
    total = Decimal("0")
    for item in items:
        qty = Decimal(str(item.quantity or 0))
        unit = Decimal(str(item.unit_price or 0))
        total += qty * unit
    return total


def _subscription_rows(session: Session) -> list[tuple[Subscription, Decimal, str | None]]:
    """Every active subscription with its per-cycle amount and plan name.

    Single join pass — avoids ORM lazy loads per row.
    """
    rows = session.execute(
        sa.select(Subscription, SubscriptionPlan.name)
        .outerjoin(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
        .where(Subscription.status == "active")
    ).all()
    out: list[tuple[Subscription, Decimal, str | None]] = []
    for sub, plan_name in rows:
        amount = _recurring_amount(list(sub.items))
        out.append((sub, amount, plan_name))
    return out


def _active_on(sub: Subscription, as_of: dt.date) -> bool:
    """Was this (currently-active) subscription active on `as_of`?"""
    if sub.start_date is not None and sub.start_date > as_of:
        return False
    if sub.expiry_date is not None and sub.expiry_date <= as_of:
        return False
    return True


def mrr_snapshot(session: Session, as_of: dt.date) -> dict:
    """MRR + ARR + plan/frequency breakdown at a point in time."""
    mrr = Decimal("0")
    by_plan: dict[str, Decimal] = {}
    by_frequency: dict[str, Decimal] = {}
    counted = 0

    for sub, cycle_amount, plan_name in _subscription_rows(session):
        if not _active_on(sub, as_of):
            continue
        monthly = cycle_amount * monthly_factor(sub.billing_frequency)
        mrr += monthly
        counted += 1
        plan_key = plan_name or "No plan"
        by_plan[plan_key] = by_plan.get(plan_key, Decimal("0")) + monthly
        freq = sub.billing_frequency or "monthly"
        by_frequency[freq] = by_frequency.get(freq, Decimal("0")) + monthly

    q = lambda v: v.quantize(CENTS)
    return {
        "as_of": as_of.isoformat(),
        "subscription_count": counted,
        "mrr": q(mrr),
        "arr": q(mrr * MONTHS_PER_YEAR),
        "by_plan": [
            {"plan": k, "mrr": q(v)} for k, v in sorted(by_plan.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "by_frequency": [
            {"frequency": k, "mrr": q(v)} for k, v in sorted(by_frequency.items())
        ],
    }


def mrr_trend(
    session: Session, date_from: dt.date, date_to: dt.date
) -> list[dict]:
    """Monthly MRR snapshots from `date_from` to `date_to` (inclusive).

    One DB pass over active subscriptions; each month-end point evaluates
    the start/expiry window in Python — dialect-agnostic.
    """
    rows = _subscription_rows(session)

    def month_ends() -> list[dt.date]:
        y, m = date_from.year, date_from.month
        points: list[dt.date] = []
        while True:
            if m == 12:
                end = dt.date(y, 12, 31)
            else:
                end = dt.date(y, m + 1, 1) - dt.timedelta(days=1)
            points.append(min(end, date_to))
            if end >= date_to:
                break
            m += 1
            if m == 13:
                m, y = 1, y + 1
        return points

    q = lambda v: v.quantize(CENTS)
    points = []
    for as_of in month_ends():
        mrr = sum(
            amount * monthly_factor(sub.billing_frequency)
            for sub, amount, _ in rows
            if _active_on(sub, as_of)
        )
        points.append({"period": as_of.isoformat()[:7], "as_of": as_of.isoformat(), "mrr": q(mrr), "arr": q(mrr * MONTHS_PER_YEAR)})
    return points
