"""MRR/ARR normalization across every supported billing frequency."""

import datetime as dt
from decimal import Decimal

from app.core.time import business_date
from app.modules.finance_intelligence.analytics import mrr_arr

from finance_seed import customer, plan, subscription

CENTS = Decimal("0.01")


def test_mrr_normalizes_all_frequencies(session):
    c = customer(session)
    subscription(session, customer=c, frequency="monthly", items=(("1", "1200.00"),))
    subscription(session, customer=c, frequency="yearly", items=(("1", "12000.00"),))
    subscription(session, customer=c, frequency="weekly", items=(("1", "100.00"),))
    subscription(session, customer=c, frequency="daily", items=(("1", "10.00"),))

    snap = mrr_arr.mrr_snapshot(session, business_date())

    expected = (
        Decimal("1200.00")                      # monthly ×1
        + Decimal("12000.00") / 12              # yearly ÷12 = 1000
        + Decimal("100.00") * Decimal(52) / 12  # weekly ×52/12 = 433.33…
        + Decimal("10.00") * Decimal(365) / 12  # daily ×365/12 = 304.16…
    )
    assert snap["mrr"] == expected.quantize(CENTS)
    assert snap["arr"] == (snap["mrr"] * 12).quantize(CENTS)
    assert snap["subscription_count"] == 4
    assert {r["frequency"] for r in snap["by_frequency"]} == {
        "daily", "weekly", "monthly", "yearly",
    }


def test_mrr_excludes_non_active_statuses(session):
    c = customer(session)
    subscription(session, customer=c, status="paused", items=(("1", "5000.00"),))
    subscription(session, customer=c, status="closed", items=(("1", "5000.00"),))
    subscription(session, customer=c, status="draft", items=(("1", "5000.00"),))
    subscription(session, customer=c, status="confirmed", items=(("1", "5000.00"),))

    snap = mrr_arr.mrr_snapshot(session, business_date())
    assert snap["mrr"] == Decimal("0.00")
    assert snap["subscription_count"] == 0


def test_mrr_uses_line_quantity_times_unit_price(session):
    c = customer(session)
    subscription(
        session, customer=c,
        items=(("3", "500.00"), ("2", "250.00")),  # 1500 + 500
    )
    snap = mrr_arr.mrr_snapshot(session, business_date())
    assert snap["mrr"] == Decimal("2000.00")


def test_mrr_breaks_down_by_plan(session):
    c = customer(session)
    p1 = plan(session, name="Pro")
    p2 = plan(session, name="Enterprise")
    subscription(session, customer=c, plan=p1, items=(("1", "1000.00"),))
    subscription(session, customer=c, plan=p2, items=(("1", "3000.00"),))
    subscription(session, customer=c, plan=None, items=(("1", "500.00"),))

    snap = mrr_arr.mrr_snapshot(session, business_date())
    by_plan = {r["plan"]: r["mrr"] for r in snap["by_plan"]}
    assert by_plan["Pro"] == Decimal("1000.00")
    assert by_plan["Enterprise"] == Decimal("3000.00")
    assert by_plan["No plan"] == Decimal("500.00")
    assert snap["mrr"] == Decimal("4500.00")


def test_mrr_never_double_counts_a_subscription(session):
    c = customer(session)
    subscription(session, customer=c, items=(("1", "999.00"),))
    snap = mrr_arr.mrr_snapshot(session, business_date())
    assert snap["subscription_count"] == 1
    assert snap["mrr"] == Decimal("999.00")


def test_mrr_trend_respects_start_and_expiry(session):
    today = business_date()
    c = customer(session)
    # active for the whole window
    subscription(session, customer=c, items=(("1", "1000.00"),), start_offset_days=400)
    # starts mid-window
    subscription(session, customer=c, items=(("1", "500.00"),), start_offset_days=15)
    # expired before window start (still 'active' status — tests date windowing)
    subscription(
        session, customer=c, items=(("1", "9999.00"),),
        start_offset_days=400, expiry=today - dt.timedelta(days=300),
    )

    from_ = today - dt.timedelta(days=90)
    points = mrr_arr.mrr_trend(session, from_, today)
    assert len(points) >= 3
    # earliest month-ends: only the long-running sub counts
    assert points[0]["mrr"] == Decimal("1000.00")
    # latest point: long-running + recently started
    assert points[-1]["mrr"] == Decimal("1500.00")
    assert points[-1]["arr"] == Decimal("18000.00")
