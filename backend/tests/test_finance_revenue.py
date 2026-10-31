"""Revenue trends, period-over-period growth, breakdowns."""

import datetime as dt
from decimal import Decimal

from app.core.time import business_date
from app.modules.finance_intelligence.analytics import revenue

from finance_seed import customer, invoice, payment, plan, subscription

CENTS = Decimal("0.01")


def test_trends_separate_invoiced_from_collected(session):
    today = business_date()
    c = customer(session)
    inv = invoice(session, customer=c, total="1000.00", issue_date=today)
    payment(session, invoice=inv, amount="600.00", paid_at=dt.datetime.now(dt.timezone.utc))

    out = revenue.revenue_trends(
        session, interval="month", date_from=today - dt.timedelta(days=30), date_to=today
    )
    assert out["totals"]["invoiced"] == Decimal("1000.00")
    assert out["totals"]["collected"] == Decimal("600.00")
    # invoiced and collected are never conflated
    assert out["totals"]["invoiced"] != out["totals"]["collected"]


def test_trends_exclude_draft_cancelled_and_voided(session):
    today = business_date()
    c = customer(session)
    invoice(session, customer=c, total="500.00", status="draft", issue_date=today)
    invoice(session, customer=c, total="700.00", status="cancelled", issue_date=today)
    real = invoice(session, customer=c, total="1000.00", status="confirmed", issue_date=today)
    payment(session, invoice=real, amount="300.00", status="voided")
    payment(session, invoice=real, amount="200.00", status="posted")

    out = revenue.revenue_trends(
        session, interval="month", date_from=today, date_to=today
    )
    assert out["totals"]["invoiced"] == Decimal("1000.00")
    assert out["totals"]["collected"] == Decimal("200.00")


def test_growth_pct_compares_same_length_previous_period(session):
    today = business_date()
    c = customer(session)
    # current 10-day window: 1000 collected; previous window: 500
    cur = invoice(session, customer=c, total="1000.00", issue_date=today)
    payment(session, invoice=cur, amount="1000.00")
    prev_inv = invoice(session, customer=c, total="400.00", issue_date=today - dt.timedelta(days=11))
    payment(
        session, invoice=prev_inv, amount="500.00",
        paid_at=dt.datetime.combine(today - dt.timedelta(days=11), dt.time(12), tzinfo=dt.timezone.utc),
    )

    out = revenue.revenue_trends(
        session, interval="day",
        date_from=today - dt.timedelta(days=9), date_to=today,
    )
    assert out["growth_pct"]["collected"] == Decimal("100.00")  # 1000 vs 500
    assert out["growth_pct"]["invoiced"] == Decimal("150.00")   # 1000 vs 400
    assert out["previous_range"]["to"] == (today - dt.timedelta(days=10)).isoformat()


def test_growth_pct_none_when_previous_zero(session):
    today = business_date()
    c = customer(session)
    inv = invoice(session, customer=c, total="100.00", issue_date=today)
    payment(session, invoice=inv, amount="100.00")

    out = revenue.revenue_trends(
        session, interval="month",
        date_from=today - dt.timedelta(days=9), date_to=today,
    )
    assert out["growth_pct"]["invoiced"] is None
    assert out["growth_pct"]["collected"] is None


def test_breakdown_by_plan_product_customer(session):
    today = business_date()
    c1, c2 = customer(session, "Acme"), customer(session, "Beta")
    p1, p2 = plan(session, "Pro"), plan(session, "Enterprise")
    s1 = subscription(session, customer=c1, plan=p1)
    s2 = subscription(session, customer=c2, plan=p2)
    invoice(session, customer=c1, subscription=s1, total="1000.00", issue_date=today,
            lines=[(p1.product_id, 1, "1000", "1000.00")])
    invoice(session, customer=c2, subscription=s2, total="3000.00", issue_date=today,
            lines=[(p2.product_id, 1, "3000", "3000.00")])
    invoice(session, customer=c1, subscription=None, total="200.00", issue_date=today)

    lo, hi = today - dt.timedelta(days=10), today
    by_plan = revenue.breakdown(session, by="plan", date_from=lo, date_to=hi)
    plan_map = {r["key"]: r["amount"] for r in by_plan}
    assert plan_map["Enterprise"] == Decimal("3000.00")
    assert plan_map["Pro"] == Decimal("1000.00")
    assert plan_map["No plan"] == Decimal("200.00")

    by_product = revenue.breakdown(session, by="product", date_from=lo, date_to=hi)
    assert by_product[0]["amount"] == Decimal("3000.00")

    by_customer = revenue.breakdown(session, by="customer", date_from=lo, date_to=hi)
    cust_map = {r["key"]: r["amount"] for r in by_customer}
    assert cust_map["Beta"] == Decimal("3000.00")
    assert cust_map["Acme"] == Decimal("1200.00")


def test_breakdown_by_payment_method_counts_cash(session):
    today = business_date()
    c = customer(session)
    inv = invoice(session, customer=c, total="1000.00", issue_date=today)
    payment(session, invoice=inv, amount="600.00", method="upi")
    payment(session, invoice=inv, amount="400.00", method="bank_transfer")
    payment(session, invoice=inv, amount="50.00", method="cash", status="voided")

    rows = revenue.breakdown(
        session, by="payment_method",
        date_from=today - dt.timedelta(days=5), date_to=today,
    )
    methods = {r["key"]: r["amount"] for r in rows}
    assert methods["upi"] == Decimal("600.00")
    assert methods["bank_transfer"] == Decimal("400.00")
    assert "cash" not in methods  # voided payment excluded
