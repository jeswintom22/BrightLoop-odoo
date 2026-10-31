"""P3 — quotation & subscription lifecycle service.

Lifecycle:  draft -> confirmed -> active <-> paused -> closed
Quotation:  draft -> sent -> confirmed -> converted | expired | cancelled
Billing only sees subscriptions with status='active' (contract in
DbSubscriptionProvider), so paused/closed/draft/confirmed subs are never
invoiced — transitions are enforced here.
"""

import datetime as dt
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.time import business_date
from ...modules.billing.numbering import allocate_number
from .models import (
    Quotation,
    QuotationLine,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionItem,
)

CENTS = Decimal("0.01")
FREQUENCIES = ("daily", "weekly", "monthly", "yearly")


def _add_months(d: dt.date, months: int) -> dt.date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.date(year, month, day)


def add_period(d: dt.date, frequency: str) -> dt.date:
    if frequency == "daily":
        return d + dt.timedelta(days=1)
    if frequency == "weekly":
        return d + dt.timedelta(weeks=1)
    if frequency == "yearly":
        return _add_months(d, 12)
    return _add_months(d, 1)


# --- catalog pricing helpers (P2 — int PKs) ---------------------------------


def _catalog_price(session: Session, *, product_id, variant_id, plan_id):
    """unit_price + tax_rate from P2's real tables. Returns (Decimal, Decimal)."""
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.subscription_plan import SubscriptionPlan

    unit = Decimal("0")
    tax_rate = Decimal("0")
    product = None

    if variant_id is not None:
        variant = session.get(ProductVariant, variant_id)
        if variant is not None:
            unit = Decimal(str(variant.sales_price))
            product = variant.product
    if product is None and product_id is not None:
        product = session.get(Product, product_id)
        if product is not None and unit == 0:
            unit = Decimal(str(product.sales_price))
    if plan_id is not None:
        plan = session.get(SubscriptionPlan, plan_id)
        if plan is not None:
            unit = Decimal(str(plan.price))  # plan price governs when present
            if plan.tax_id and plan.tax:
                tax_rate = Decimal(str(plan.tax.tax_percentage))
    if tax_rate == 0 and product is not None and product.tax_id and product.tax:
        tax_rate = Decimal(str(product.tax.tax_percentage))
    return unit, tax_rate


# --- quotation templates ------------------------------------------------------


def create_template(
    session: Session, *, name: str, description: str | None,
    validity_days: int, lines: list[dict],
) -> QuotationTemplate:
    if not lines:
        raise AppError("VALIDATION", "A template needs at least one line", 400)
    tpl = QuotationTemplate(
        name=name, description=description, validity_days=validity_days
    )
    for i, line in enumerate(lines):
        tpl.lines.append(
            QuotationTemplateLine(
                product_id=line.get("product_id"),
                plan_id=line.get("plan_id"),
                description=line.get("description", ""),
                quantity=line.get("quantity", 1),
                position=i,
            )
        )
    session.add(tpl)
    session.flush()
    return tpl


# --- quotations ----------------------------------------------------------------


def create_quotation(
    session: Session, *, customer_id: uuid.UUID, template_id: uuid.UUID | None,
    lines: list[dict] | None, notes: str | None,
) -> Quotation:
    today = business_date()
    source_lines: list[dict] = []
    validity_days = 15

    if template_id is not None:
        tpl = session.get(QuotationTemplate, template_id)
        if tpl is None or not tpl.is_active:
            raise AppError("NOT_FOUND", "Quotation template not found", 404)
        validity_days = tpl.validity_days
        source_lines = [
            {
                "product_id": l.product_id,
                "plan_id": l.plan_id,
                "description": l.description,
                "quantity": l.quantity,
            }
            for l in tpl.lines
        ]
    elif lines:
        source_lines = lines

    if not source_lines:
        raise AppError("VALIDATION", "Quotation needs at least one line", 400)

    issue_year = today.year
    quotation = Quotation(
        quotation_number=allocate_number(session, "quotation", issue_year),
        customer_id=customer_id,
        template_id=template_id,
        status="draft",
        issue_date=today,
        valid_until=today + dt.timedelta(days=validity_days),
        notes=notes,
    )

    subtotal = tax_total = Decimal("0")
    for i, line in enumerate(source_lines):
        qty = Decimal(str(line.get("quantity", 1)))
        if qty <= 0:
            raise AppError("VALIDATION", "Line quantity must be positive", 400)
        unit, tax_rate = _catalog_price(
            session,
            product_id=line.get("product_id"),
            variant_id=line.get("product_variant_id"),
            plan_id=line.get("plan_id"),
        )
        line_subtotal = (unit * qty).quantize(CENTS)
        line_tax = (line_subtotal * tax_rate / Decimal("100")).quantize(CENTS)
        quotation.lines.append(
            QuotationLine(
                product_id=line.get("product_id"),
                product_variant_id=line.get("product_variant_id"),
                plan_id=line.get("plan_id"),
                description=line.get("description") or "",
                quantity=qty,
                unit_price=unit,
                tax_rate=tax_rate,
                line_total=(line_subtotal + line_tax).quantize(CENTS),
                position=i,
            )
        )
        subtotal += line_subtotal
        tax_total += line_tax

    quotation.subtotal = subtotal
    quotation.tax_total = tax_total
    quotation.discount_total = Decimal("0")
    quotation.total_amount = subtotal + tax_total
    session.add(quotation)
    session.flush()
    return quotation


def send_quotation(session: Session, quotation: Quotation) -> Quotation:
    if quotation.status != "draft":
        raise AppError("INVALID_STATE", "Only draft quotations can be sent", 409)
    quotation.status = "sent"
    session.flush()
    return quotation


def confirm_quotation(session: Session, quotation: Quotation) -> Quotation:
    if quotation.status in ("expired", "cancelled", "converted"):
        raise AppError(
            "INVALID_STATE", f"Quotation is {quotation.status}", 409
        )
    today = business_date()
    if quotation.valid_until < today:
        quotation.status = "expired"  # expired quotations can never be confirmed
        session.flush()
        raise AppError("QUOTATION_EXPIRED", "Quotation has expired", 409)
    if quotation.status == "confirmed":
        return quotation
    quotation.status = "confirmed"
    session.flush()
    return quotation


# --- subscriptions --------------------------------------------------------------


def convert_to_subscription(
    session: Session,
    quotation: Quotation,
    *,
    start_date: dt.date | None = None,
    payment_terms: str | None = None,
) -> Subscription:
    if quotation.status != "confirmed":
        raise AppError(
            "INVALID_STATE",
            "Only a confirmed quotation can be converted (confirm it first)",
            409,
        )
    today = business_date()
    start = start_date or today
    plan_ids = [l.plan_id for l in quotation.lines if l.plan_id is not None]
    plan_id = plan_ids[0] if plan_ids else None

    from app.models.subscription_plan import SubscriptionPlan

    plan = session.get(SubscriptionPlan, plan_id) if plan_id else None
    frequency = plan.billing_frequency if plan else "monthly"

    sub = Subscription(
        subscription_number=allocate_number(session, "subscription", today.year),
        customer_id=quotation.customer_id,
        plan_id=plan_id,
        quotation_id=quotation.id,
        status="active",  # conversion activates (scenario: convert -> active)
        billing_frequency=frequency,
        start_date=start,
        expiry_date=_add_months(start, 12),
        next_billing_date=start,
        payment_terms=payment_terms,
    )
    for i, line in enumerate(quotation.lines):
        sub.items.append(
            SubscriptionItem(
                product_id=line.product_id,
                product_variant_id=line.product_variant_id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate=line.tax_rate,
                position=i,
            )
        )
    quotation.status = "converted"
    session.add(sub)
    session.flush()
    return sub


def _get(session: Session, subscription_id: uuid.UUID) -> Subscription:
    sub = session.get(Subscription, subscription_id)
    if sub is None:
        raise AppError("NOT_FOUND", "Subscription not found", 404)
    return sub


def _plan_flags(session: Session, sub: Subscription):
    if sub.plan_id is None:
        return None
    from app.models.subscription_plan import SubscriptionPlan

    return session.get(SubscriptionPlan, sub.plan_id)


def activate(session: Session, subscription_id: uuid.UUID, *, start_date=None):
    sub = _get(session, subscription_id)
    if sub.status not in ("draft", "confirmed"):
        raise AppError(
            "INVALID_STATE", f"Cannot activate a {sub.status} subscription", 409
        )
    today = business_date()
    sub.status = "active"
    sub.start_date = start_date or today
    sub.next_billing_date = sub.start_date
    if sub.expiry_date is None:
        sub.expiry_date = _add_months(sub.start_date, 12)
    session.flush()
    return sub


def pause(session: Session, subscription_id: uuid.UUID):
    sub = _get(session, subscription_id)
    if sub.status != "active":
        raise AppError("INVALID_STATE", "Only active subscriptions can pause", 409)
    plan = _plan_flags(session, sub)
    if plan is not None and not plan.allow_pause:
        raise AppError("FORBIDDEN", "Plan does not allow pausing", 409)
    sub.status = "paused"
    session.flush()
    return sub


def resume(session: Session, subscription_id: uuid.UUID):
    sub = _get(session, subscription_id)
    if sub.status != "paused":
        raise AppError("INVALID_STATE", "Only paused subscriptions can resume", 409)
    if sub.expiry_date is not None and sub.expiry_date < business_date():
        raise AppError("INVALID_STATE", "Subscription expired — renew instead", 409)
    sub.status = "active"
    session.flush()
    return sub


def renew(session: Session, subscription_id: uuid.UUID):
    sub = _get(session, subscription_id)
    if sub.status not in ("active", "paused", "closed"):
        raise AppError("INVALID_STATE", f"Cannot renew a {sub.status} subscription", 409)
    plan = _plan_flags(session, sub)
    if plan is not None and not plan.allow_renewal:
        raise AppError("FORBIDDEN", "Plan does not allow renewal", 409)
    today = business_date()
    base = max(sub.expiry_date or today, today)
    sub.expiry_date = add_period(base, sub.billing_frequency)
    sub.status = "active"
    if sub.next_billing_date is None or sub.next_billing_date < today:
        sub.next_billing_date = today
    session.flush()
    return sub


def close(session: Session, subscription_id: uuid.UUID):
    sub = _get(session, subscription_id)
    if sub.status == "closed":
        raise AppError("INVALID_STATE", "Already closed", 409)
    plan = _plan_flags(session, sub)
    if (
        sub.status == "active"
        and plan is not None
        and not plan.allow_early_closure
    ):
        raise AppError("FORBIDDEN", "Plan does not allow early closure", 409)
    sub.status = "closed"
    session.flush()
    return sub


def close_expired(session: Session, as_of: dt.date | None = None) -> int:
    """Auto-closure sweep — closes active subs past expiry whose plan sets
    auto_closure. Called by the internal billing run before due-scan."""
    from app.models.subscription_plan import SubscriptionPlan

    as_of = as_of or business_date()
    rows = session.scalars(
        sa.select(Subscription).where(
            Subscription.status == "active",
            Subscription.expiry_date.is_not(None),
            Subscription.expiry_date < as_of,
        )
    ).all()
    closed = 0
    for sub in rows:
        plan = session.get(SubscriptionPlan, sub.plan_id) if sub.plan_id else None
        if plan is not None and not plan.automatic_closure:
            continue
        sub.status = "closed"
        closed += 1
    if closed:
        session.flush()
    return closed
