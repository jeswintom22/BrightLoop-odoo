"""Deterministic revenue-at-risk detection — backend business logic only.

Rules (each emits structured ``RiskRecord`` dicts; no LLM involvement in
detection, scoring or severity):

1. ``high_value_overdue``    — a confirmed invoice overdue with outstanding
                               ≥ HIGH_VALUE_THRESHOLD (default ₹10,000).
2. ``multiple_overdue``      — customer with ≥ 2 currently-overdue invoices.
3. ``repeated_late_payments``— ≥ 2 posted payments that settled an invoice
                               after its due date (payment behaviour, not
                               just current exposure).
4. ``renewal_unpaid``        — active subscription billing within
                               RENEWAL_WINDOW_DAYS whose customer already
                               carries overdue invoices.
5. ``large_exposure``        — customer outstanding balance > max(
                               LARGE_EXPOSURE_MRR_MULTIPLE × their monthly
                               recurring revenue, collected over the last
                               90 days). Catches exposure growth beyond
                               demonstrated payment capacity.

Severity scoring (deterministic): points accrue from days overdue, amount
vs. threshold and invoice count; high ≥ 4, medium ≥ 2, else low.
Paid/cancelled invoices and voided payments never produce risks.
"""

import datetime as dt
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ....core.time import business_date
from ...billing.models import Invoice, Payment
from ...subscriptions.models import Subscription
from ...auth.models import Customer
from .mrr_arr import monthly_factor

CENTS = Decimal("0.01")

HIGH_VALUE_THRESHOLD = Decimal("10000")
RENEWAL_WINDOW_DAYS = 30
LATE_PAYMENT_MIN_COUNT = 2
LARGE_EXPOSURE_MRR_MULTIPLE = Decimal("3")

SEVERITIES = ("high", "medium", "low")
CATEGORIES = (
    "high_value_overdue",
    "multiple_overdue",
    "repeated_late_payments",
    "renewal_unpaid",
    "large_exposure",
)


def _severity(*, days_overdue: int, outstanding: Decimal, invoice_count: int) -> str:
    score = 0
    if days_overdue >= 60:
        score += 3
    elif days_overdue >= 30:
        score += 2
    elif days_overdue >= 1:
        score += 1
    if outstanding >= HIGH_VALUE_THRESHOLD * 5:
        score += 3
    elif outstanding >= HIGH_VALUE_THRESHOLD:
        score += 2
    elif outstanding >= HIGH_VALUE_THRESHOLD / 2:
        score += 1
    if invoice_count >= 3:
        score += 2
    elif invoice_count >= 2:
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


_ACTIONS = {
    "high_value_overdue": "Contact the customer immediately about this high-value overdue invoice; escalate per collections policy.",
    "multiple_overdue": "Review the account's full outstanding position and contact the customer before issuing further invoices.",
    "repeated_late_payments": "Flag account for proactive payment follow-up; consider shorter payment terms or upfront collection.",
    "renewal_unpaid": "Contact the customer to settle outstanding invoices before the upcoming renewal bills.",
    "large_exposure": "Escalate to a finance manager; the outstanding balance exceeds demonstrated payment capacity.",
}


def _record(**kw) -> dict:
    kw.setdefault("outstanding_amount", Decimal("0"))
    kw["outstanding_amount"] = Decimal(str(kw["outstanding_amount"])).quantize(CENTS)
    return kw


def detect_risks(session: Session, *, as_of: dt.date | None = None) -> list[dict]:
    today = as_of or business_date()
    risks: list[dict] = []
    outstanding_col = Invoice.total_amount - Invoice.amount_paid

    # ── shared base queries ─────────────────────────────────────────────────
    overdue_rows = session.execute(
        sa.select(Invoice, Customer.name)
        .outerjoin(Customer, Invoice.customer_id == Customer.id)
        .where(
            Invoice.status == "confirmed",
            Invoice.due_date < today,
            outstanding_col > 0,
        )
        .order_by(Invoice.due_date)
    ).all()

    per_customer: dict[uuid.UUID, list] = {}
    for inv, cust_name in overdue_rows:
        per_customer.setdefault(inv.customer_id, []).append((inv, cust_name))

    # ── rule 1: high_value_overdue ──────────────────────────────────────────
    for inv, cust_name in overdue_rows:
        outstanding = inv.total_amount - inv.amount_paid
        if outstanding < HIGH_VALUE_THRESHOLD:
            continue
        days = (today - inv.due_date).days
        risks.append(
            _record(
                customer_id=inv.customer_id,
                customer_name=cust_name,
                subscription_id=inv.subscription_id,
                invoice_id=inv.id,
                invoice_number=inv.invoice_number,
                outstanding_amount=outstanding,
                days_overdue=days,
                risk_category="high_value_overdue",
                severity=_severity(days_overdue=days, outstanding=outstanding, invoice_count=1),
                detection_reason=(
                    f"Invoice {inv.invoice_number} is {days} day(s) overdue with "
                    f"{outstanding.quantize(CENTS)} outstanding (≥ {HIGH_VALUE_THRESHOLD} threshold)."
                ),
                recommended_action=_ACTIONS["high_value_overdue"],
            )
        )

    # ── rule 2: multiple_overdue ────────────────────────────────────────────
    for customer_id, items in per_customer.items():
        if len(items) < 2:
            continue
        total = sum((i.total_amount - i.amount_paid for i, _ in items), Decimal("0"))
        oldest_days = max((today - i.due_date).days for i, _ in items)
        cust_name = items[0][1]
        risks.append(
            _record(
                customer_id=customer_id,
                customer_name=cust_name,
                subscription_id=None,
                invoice_id=items[0][0].id,
                invoice_number=items[0][0].invoice_number,
                outstanding_amount=total,
                days_overdue=oldest_days,
                risk_category="multiple_overdue",
                severity=_severity(days_overdue=oldest_days, outstanding=total, invoice_count=len(items)),
                detection_reason=(
                    f"Customer has {len(items)} overdue invoices totalling "
                    f"{total.quantize(CENTS)} outstanding; oldest is {oldest_days} day(s) overdue."
                ),
                recommended_action=_ACTIONS["multiple_overdue"],
            )
        )

    # ── rule 3: repeated_late_payments ──────────────────────────────────────
    late_rows = session.execute(
        sa.select(
            Invoice.customer_id,
            Customer.name,
            sa.func.count(Payment.id).label("late_count"),
            sa.func.sum(Payment.amount).label("late_amount"),
        )
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .outerjoin(Customer, Invoice.customer_id == Customer.id)
        .where(
            Payment.status == "posted",
            # paid strictly after the invoice's due date -> a "late" payment.
            # func.date() extracts the calendar date on both SQLite and Postgres.
            sa.func.date(Payment.paid_at) > Invoice.due_date,
        )
        .group_by(Invoice.customer_id, Customer.name)
        .having(sa.func.count(Payment.id) >= LATE_PAYMENT_MIN_COUNT)
    ).all()
    for customer_id, cust_name, late_count, late_amount in late_rows:
        risks.append(
            _record(
                customer_id=customer_id,
                customer_name=cust_name,
                subscription_id=None,
                invoice_id=None,
                invoice_number=None,
                outstanding_amount=Decimal(str(late_amount or 0)),
                days_overdue=0,
                risk_category="repeated_late_payments",
                severity="medium" if late_count >= 3 else "low",
                detection_reason=(
                    f"{late_count} posted payments settled invoices after their "
                    f"due dates (₹ equivalent {Decimal(str(late_amount or 0)).quantize(CENTS)} paid late)."
                ),
                recommended_action=_ACTIONS["repeated_late_payments"],
            )
        )

    # ── rule 4: renewal_unpaid ──────────────────────────────────────────────
    window_end = today + dt.timedelta(days=RENEWAL_WINDOW_DAYS)
    renewals = session.execute(
        sa.select(Subscription, Customer.name)
        .outerjoin(Customer, Subscription.customer_id == Customer.id)
        .where(
            Subscription.status == "active",
            Subscription.next_billing_date.is_not(None),
            Subscription.next_billing_date >= today,
            Subscription.next_billing_date <= window_end,
            Subscription.customer_id.in_(list(per_customer) or [uuid.UUID(int=0)]),
        )
    ).all()
    for sub, cust_name in renewals:
        items = per_customer.get(sub.customer_id, [])
        total = sum((i.total_amount - i.amount_paid for i, _ in items), Decimal("0"))
        oldest_days = max((today - i.due_date).days for i, _ in items)
        risks.append(
            _record(
                customer_id=sub.customer_id,
                customer_name=cust_name,
                subscription_id=sub.id,
                invoice_id=items[0][0].id if items else None,
                invoice_number=items[0][0].invoice_number if items else None,
                outstanding_amount=total,
                days_overdue=oldest_days,
                risk_category="renewal_unpaid",
                severity=_severity(days_overdue=oldest_days, outstanding=total, invoice_count=len(items)),
                detection_reason=(
                    f"Subscription {sub.subscription_number} bills on "
                    f"{sub.next_billing_date.isoformat()} while the customer has "
                    f"{len(items)} overdue invoice(s) totalling {total.quantize(CENTS)}."
                ),
                recommended_action=_ACTIONS["renewal_unpaid"],
            )
        )

    # ── rule 5: large_exposure ──────────────────────────────────────────────
    start90 = today - dt.timedelta(days=90)
    lo90, hi90 = (
        dt.datetime.combine(start90, dt.time.min, tzinfo=dt.timezone.utc),
        dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc),
    )
    collected90 = dict(
        session.execute(
            sa.select(Invoice.customer_id, sa.func.sum(Payment.amount))
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(
                Payment.status == "posted",
                Payment.paid_at >= lo90,
                Payment.paid_at <= hi90,
            )
            .group_by(Invoice.customer_id)
        ).all()
    )
    monthly_recurring: dict[uuid.UUID, Decimal] = {}
    active_subs = session.execute(
        sa.select(Subscription).where(Subscription.status == "active")
    ).scalars().all()
    for sub in active_subs:
        cycle = sum(
            (Decimal(str(i.quantity or 0)) * Decimal(str(i.unit_price or 0)) for i in sub.items),
            Decimal("0"),
        )
        monthly_recurring[sub.customer_id] = monthly_recurring.get(
            sub.customer_id, Decimal("0")
        ) + cycle * monthly_factor(sub.billing_frequency)

    open_rows = session.execute(
        sa.select(
            Invoice.customer_id,
            Customer.name,
            sa.func.sum(outstanding_col).label("outstanding"),
        )
        .outerjoin(Customer, Invoice.customer_id == Customer.id)
        .where(Invoice.status == "confirmed", outstanding_col > 0)
        .group_by(Invoice.customer_id, Customer.name)
    ).all()
    for customer_id, cust_name, outstanding in open_rows:
        outstanding = Decimal(str(outstanding))
        if outstanding <= 0:
            continue
        capacity = max(
            monthly_recurring.get(customer_id, Decimal("0")) * LARGE_EXPOSURE_MRR_MULTIPLE,
            Decimal(str(collected90.get(customer_id, Decimal("0")))),
        )
        if outstanding <= capacity or capacity <= 0:
            continue
        cust_overdue = per_customer.get(customer_id, [])
        oldest_days = max(((today - i.due_date).days for i, _ in cust_overdue), default=0)
        risks.append(
            _record(
                customer_id=customer_id,
                customer_name=cust_name,
                subscription_id=None,
                invoice_id=None,
                invoice_number=None,
                outstanding_amount=outstanding,
                days_overdue=oldest_days,
                risk_category="large_exposure",
                severity=_severity(days_overdue=oldest_days, outstanding=outstanding, invoice_count=len(cust_overdue)),
                detection_reason=(
                    f"Outstanding balance {outstanding.quantize(CENTS)} exceeds "
                    f"capacity gauge {capacity.quantize(CENTS)} (3× monthly recurring "
                    f"revenue or 90-day collections, whichever is higher)."
                ),
                recommended_action=_ACTIONS["large_exposure"],
            )
        )

    order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda r: (order.get(r["severity"], 3), -r["outstanding_amount"]))
    for i, r in enumerate(risks):
        r["risk_index"] = i
    return risks


def risk_summary(risks: list[dict]) -> dict:
    by_severity = {"high": 0, "medium": 0, "low": 0}
    by_category = {c: 0 for c in CATEGORIES}
    total_at_risk = Decimal("0")
    customers: set[str] = set()
    for r in risks:
        by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1
        by_category[r["risk_category"]] = by_category.get(r["risk_category"], 0) + 1
        total_at_risk += Decimal(str(r["outstanding_amount"]))
        customers.add(str(r["customer_id"]))
    return {
        "total_risks": len(risks),
        "customers_at_risk": len(customers),
        "total_outstanding_at_risk": total_at_risk.quantize(CENTS),
        "by_severity": by_severity,
        "by_category": by_category,
    }
