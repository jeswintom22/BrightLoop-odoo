"""Collection forecast — expected billings vs expected collections."""

import datetime as dt
from decimal import Decimal

from app.core.time import business_date
from app.modules.finance_intelligence.analytics import forecasting

from finance_seed import customer, invoice, payment, subscription


def test_expected_billings_uses_subscription_cycle_amount(session):
    c = customer(session)
    subscription(
        session, customer=c, frequency="monthly",
        items=(("2", "500.00"),),           # 1000 + 0% tax
        next_billing_offset_days=10,
    )
    out = forecasting.forecast(session, horizon_days=30)
    assert out["expected_billings_count"] == 1
    assert out["expected_billings"] == Decimal("1000.00")
    row = out["upcoming_billings"][0]
    assert row["expected_amount"] == Decimal("1000.00")


def test_expected_billings_includes_line_tax(session):
    c = customer(session)
    sub = subscription(
        session, customer=c, items=(("1", "1000.00"),), next_billing_offset_days=5
    )
    sub.items[0].tax_rate = Decimal("18")
    session.flush()

    out = forecasting.forecast(session, horizon_days=30)
    assert out["expected_billings"] == Decimal("1180.00")


def test_expected_billings_ignores_inactive_and_out_of_horizon(session):
    c = customer(session)
    subscription(session, customer=c, status="paused", items=(("1", "999.00"),), next_billing_offset_days=5)
    subscription(session, customer=c, items=(("1", "999.00"),), next_billing_offset_days=120)
    subscription(session, customer=c, items=(("1", "999.00"),), next_billing_offset_days=15)

    out = forecasting.forecast(session, horizon_days=30)
    assert out["expected_billings_count"] == 1  # only the active in-horizon sub


def test_expected_collections_weighted_by_realized_rate(session):
    today = business_date()
    c = customer(session)
    # 90-day window: invoiced 2000 + the new 1000 invoice = 3000;
    # collected 1500 → rate = 0.5
    hist = invoice(
        session, customer=c, total="2000.00", status="paid",
        issue_date=today - dt.timedelta(days=60), amount_paid="2000.00",
    )
    payment(
        session, invoice=hist, amount="1500.00",
        paid_at=dt.datetime.combine(today - dt.timedelta(days=60), dt.time(12), tzinfo=dt.timezone.utc),
    )
    # outstanding receivable due in horizon: 1000
    invoice(
        session, customer=c, total="1000.00", status="confirmed",
        issue_date=today - dt.timedelta(days=5),
        due_date=today + dt.timedelta(days=10), amount_paid="0",
    )

    out = forecasting.forecast(session, horizon_days=30)
    assert out["collection_rate"] == Decimal("0.5000")
    assert out["outstanding_due"] == Decimal("1000.00")
    assert out["expected_collections"] == Decimal("500.00")
    # expected billings × rate added on top
    assert out["expected_total_cash_in"] >= out["expected_collections"]


def test_forecast_distinguishes_billings_from_collections(session):
    today = business_date()
    c = customer(session)
    subscription(session, customer=c, items=(("1", "500.00"),), next_billing_offset_days=10)
    invoice(session, customer=c, total="200.00", due_date=today + dt.timedelta(days=3))

    out = forecasting.forecast(session, horizon_days=30)
    assert out["expected_billings"] == Decimal("500.00")
    assert out["outstanding_due"] == Decimal("200.00")
    assert out["expected_billings"] != out["expected_collections"]


def test_collection_rate_zero_when_no_history(session):
    assert forecasting.collection_rate(session) == Decimal("0")
