"""DB-backed provider tests.

DbPricingProvider exercises P2's real catalog models (products/taxes/discounts).
DbSubscriptionProvider / DbCustomerProvider run against contract-shaped tables
created ad hoc here (docs/architecture.md §7) — proof the adapters work the
moment P1/P3 ship matching schema.
"""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.core.time import business_date, utc_now
from app.models.discount import Discount
from app.models.product import Product
from app.models.tax import TaxConfiguration
from app.modules.billing.integrations_db import (
    DbCustomerProvider,
    DbPricingProvider,
    DbSubscriptionProvider,
)


@pytest.fixture()
def catalog(session):
    tax = TaxConfiguration(name="GST", tax_percentage=Decimal("18.00"))
    product = Product(
        name="Cloud ERP",
        product_type="service",
        sales_price=Decimal("1000.00"),
        tax=tax,
        is_active=True,
    )
    discount = Discount(
        name="Launch 10%",
        code="LAUNCH10",
        discount_type="percentage",
        discount_value=Decimal("10.00"),
        start_date=utc_now() - dt.timedelta(days=1),
        min_purchase_amount=Decimal("0.00"),
        is_active=True,
    )
    discount.applicable_products.append(product)
    session.add_all([tax, product, discount])
    session.commit()
    return product


def test_db_pricing_real_catalog(session_factory, catalog):
    pricing = DbPricingProvider(session_factory)
    bd = pricing.price_line(catalog.id, Decimal("2"))
    assert bd.unit_price == Decimal("1000.00")
    assert bd.subtotal == Decimal("2000.00")
    # 10% launch discount on 2000 -> 200; 18% GST on the discounted 1800 -> 324
    assert bd.discount_total == Decimal("200.00")
    assert bd.discount_details[0]["code"] == "LAUNCH10"
    assert bd.tax_total == Decimal("324.00")
    assert bd.line_total == Decimal("2124.00")


def test_db_pricing_inactive_or_missing_product(session_factory):
    pricing = DbPricingProvider(session_factory)
    bd = pricing.price_line(999999, Decimal("1"))
    assert bd.subtotal == Decimal("0.00")
    assert bd.line_total == Decimal("0.00")


# --- P3/P1 contract adapters — now run against the REAL shipped models ------

from app.modules.auth.models import Customer
from app.modules.subscriptions.models import Subscription, SubscriptionItem


@pytest.fixture()
def contract_schema(session):
    cid, sid = uuid.uuid4(), uuid.uuid4()
    today = business_date()
    session.add(
        Customer(
            id=cid,
            name="Contract Customer",
            email="cc@example.com",
            billing_address="1 Test Way",
        )
    )
    session.add_all(
        [
            Subscription(
                id=sid,
                subscription_number="SUB-2026-000001",
                customer_id=cid,
                status="active",
                billing_frequency="monthly",
                start_date=today - dt.timedelta(days=30),
                next_billing_date=today,
                expiry_date=None,
            ),
            Subscription(
                id=uuid.uuid4(),
                subscription_number="SUB-2026-000002",
                customer_id=cid,
                status="paused",
                billing_frequency="monthly",
                start_date=today,
                next_billing_date=today,
                expiry_date=None,
            ),
        ]
    )
    session.add(
        SubscriptionItem(
            id=uuid.uuid4(),
            subscription_id=sid,
            product_id=1,
            description="Plan seat",
            quantity=Decimal("3"),
            unit_price=Decimal("500"),
        )
    )
    session.commit()
    return {"customer_id": cid, "subscription_id": sid}


def test_db_subscription_provider_due_and_advance(session_factory, contract_schema):
    today = business_date()
    subs = DbSubscriptionProvider(session_factory)

    assert subs.count_active() == 1
    assert subs.count_due(today) == 1

    due = subs.get_due_subscriptions(today)
    assert len(due) == 1
    view = due[0]
    assert view.id == contract_schema["subscription_id"]
    assert view.billing_frequency == "monthly"
    assert len(view.lines) == 1
    assert view.lines[0].quantity == Decimal("3")

    # advance_billing_date must run inside the caller's transaction
    with session_factory() as s:
        subs.advance_billing_date(
            s, contract_schema["subscription_id"], today + dt.timedelta(days=30)
        )
        s.commit()
    assert subs.count_due(today) == 0


def test_db_customer_provider(session_factory, contract_schema):
    customers = DbCustomerProvider(session_factory)
    cid = contract_schema["customer_id"]
    view = customers.get(cid)
    assert view.name == "Contract Customer"
    assert view.email == "cc@example.com"
    many = customers.get_many([cid, uuid.uuid4()])
    assert list(many) == [cid]


# --- dashboard trend baseline ----------------------------------------------

from app.modules.billing.models import Invoice, Payment
from app.modules.billing.service_dashboard import revenue_trend


def test_trend_outstanding_carries_baseline(session):
    """Invoice issued in Jan, paid in Feb — a Feb-only filter must still
    report the outstanding correctly at each point (baseline carried in)."""
    cid, sid = uuid.uuid4(), uuid.uuid4()
    session.add(
        Invoice(
            invoice_number="INV-2026-000001",
            subscription_id=sid,
            customer_id=cid,
            status="paid",
            issue_date=dt.date(2026, 1, 10),
            due_date=dt.date(2026, 1, 17),
            period_start=dt.date(2026, 1, 1),
            period_end=dt.date(2026, 2, 1),
            currency="INR",
            subtotal=Decimal("1000.00"),
            tax_total=Decimal("180.00"),
            discount_total=Decimal("0.00"),
            total_amount=Decimal("1180.00"),
            amount_paid=Decimal("1180.00"),
        )
    )
    session.commit()
    inv = session.scalar(sa.select(Invoice))
    session.add(
        Payment(
            payment_reference="PAY-2026-000001",
            invoice_id=inv.id,
            amount=Decimal("1180.00"),
            method="upi",
            status="posted",
            paid_at=dt.datetime(2026, 2, 5, tzinfo=dt.timezone.utc),
        )
    )
    session.commit()

    trend = revenue_trend(
        session,
        interval="month",
        date_from=dt.date(2026, 2, 1),
        date_to=dt.date(2026, 2, 28),
    )
    assert len(trend.points) == 1
    p = trend.points[0]
    # Feb shows no new invoicing; the 1180 collection settles Jan's invoice:
    # baseline 1180 minus collected 1180 -> 0 outstanding. Without the
    # baseline this would read -1180.
    assert p.outstanding == Decimal("0")
    assert p.collected == Decimal("1180.00")
