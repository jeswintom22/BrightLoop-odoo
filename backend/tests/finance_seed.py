"""Shared seed helpers for finance-intelligence tests — real DB rows only."""

import datetime as dt
import uuid
from decimal import Decimal

from app.core.time import business_date
from app.modules.auth.models import Customer
from app.modules.billing.models import Invoice, InvoiceLine, Payment
from app.modules.subscriptions.models import Subscription, SubscriptionItem
from app.models.product import Product
from app.models.subscription_plan import SubscriptionPlan


def customer(session, name="Acme Ltd") -> Customer:
    c = Customer(id=uuid.uuid4(), name=name, email=f"{name.replace(' ', '.').lower()}@example.com")
    session.add(c)
    session.flush()
    return c


def plan(session, name="Pro Monthly", price="1000.00", frequency="monthly", product=None) -> SubscriptionPlan:
    product = product or Product(name=f"{name} product", sales_price=Decimal(price))
    session.add(product)
    session.flush()
    p = SubscriptionPlan(
        name=name,
        product_id=product.id,
        price=Decimal(price),
        billing_frequency=frequency,
        available_from=business_date() - dt.timedelta(days=365),
        status="active",
    )
    session.add(p)
    session.flush()
    return p


def subscription(
    session,
    *,
    customer,
    plan=None,
    frequency="monthly",
    status="active",
    items=(("1", "1000.00"),),          # (quantity, unit_price)
    start_offset_days=60,
    next_billing_offset_days=None,      # None -> today+30
    expiry=None,
) -> Subscription:
    today = business_date()
    s = Subscription(
        id=uuid.uuid4(),
        subscription_number=f"SUB-{uuid.uuid4().hex[:8].upper()}",
        customer_id=customer.id,
        plan_id=plan.id if plan else None,
        status=status,
        billing_frequency=frequency,
        start_date=today - dt.timedelta(days=start_offset_days),
        next_billing_date=today + dt.timedelta(days=30 if next_billing_offset_days is None else next_billing_offset_days),
        expiry_date=expiry,
    )
    for i, (qty, unit) in enumerate(items):
        s.items.append(
            SubscriptionItem(
                id=uuid.uuid4(),
                description="line",
                quantity=Decimal(qty),
                unit_price=Decimal(unit),
                tax_rate=Decimal("0"),
                position=i,
            )
        )
    session.add(s)
    session.flush()
    return s


def invoice(
    session,
    *,
    customer,
    subscription=None,
    status="confirmed",
    total="1000.00",
    amount_paid="0",
    issue_date=None,
    due_date=None,
    lines=None,                        # list[(product_id, qty, unit, line_total)]
) -> Invoice:
    today = business_date()
    inv = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-T-{uuid.uuid4().hex[:8].upper()}",
        subscription_id=subscription.id if subscription else None,
        customer_id=customer.id,
        status=status,
        issue_date=issue_date or today,
        due_date=due_date if due_date is not None else today,
        period_start=today - dt.timedelta(days=30),
        period_end=today,
        subtotal=Decimal(total),
        tax_total=Decimal("0"),
        discount_total=Decimal("0"),
        total_amount=Decimal(total),
        amount_paid=Decimal(amount_paid),
    )
    for i, (pid, qty, unit, line_total) in enumerate(lines or []):
        inv.lines.append(
            InvoiceLine(
                id=uuid.uuid4(),
                product_id=pid,
                description="line",
                position=i,
                quantity=Decimal(str(qty)),
                unit_price=Decimal(str(unit)),
                subtotal=Decimal(str(line_total)),
                tax_amount=Decimal("0"),
                discount_amount=Decimal("0"),
                line_total=Decimal(str(line_total)),
            )
        )
    session.add(inv)
    session.flush()
    return inv


def payment(
    session,
    *,
    invoice,
    amount="1000.00",
    method="upi",
    status="posted",
    paid_at=None,
) -> Payment:
    p = Payment(
        id=uuid.uuid4(),
        payment_reference=f"PAY-T-{uuid.uuid4().hex[:8].upper()}",
        invoice_id=invoice.id,
        amount=Decimal(amount),
        method=method,
        status=status,
        paid_at=paid_at or dt.datetime.now(dt.timezone.utc),
    )
    session.add(p)
    session.flush()
    return p
