"""Deterministic risk-detection rules and severity scoring."""

import datetime as dt
from decimal import Decimal

from app.core.time import business_date
from app.modules.finance_intelligence.analytics import risk_detection
from app.modules.finance_intelligence.analytics.risk_detection import (
    HIGH_VALUE_THRESHOLD,
)

from finance_seed import customer, invoice, payment, subscription


def _paid_at(d: dt.date):
    return dt.datetime.combine(d, dt.time(12), tzinfo=dt.timezone.utc)


def test_high_value_overdue_flagged(session):
    today = business_date()
    c = customer(session)
    invoice(
        session, customer=c, total="15000.00",
        due_date=today - dt.timedelta(days=10),
    )
    risks = risk_detection.detect_risks(session, as_of=today)
    hv = [r for r in risks if r["risk_category"] == "high_value_overdue"]
    assert len(hv) == 1
    assert hv[0]["days_overdue"] == 10
    assert hv[0]["outstanding_amount"] == Decimal("15000.00")
    assert hv[0]["recommended_action"]


def test_high_value_threshold_boundary(session):
    today = business_date()
    c = customer(session)
    invoice(
        session, customer=c,
        total=str(HIGH_VALUE_THRESHOLD - 1),
        due_date=today - dt.timedelta(days=40),
    )
    risks = risk_detection.detect_risks(session, as_of=today)
    assert not [r for r in risks if r["risk_category"] == "high_value_overdue"]


def test_multiple_overdue_aggregates_per_customer(session):
    today = business_date()
    c = customer(session)
    invoice(session, customer=c, total="100.00", due_date=today - dt.timedelta(days=5))
    invoice(session, customer=c, total="200.00", due_date=today - dt.timedelta(days=15))

    risks = risk_detection.detect_risks(session, as_of=today)
    multi = [r for r in risks if r["risk_category"] == "multiple_overdue"]
    assert len(multi) == 1
    assert multi[0]["outstanding_amount"] == Decimal("300.00")
    assert multi[0]["days_overdue"] == 15


def test_paid_and_cancelled_invoices_never_risk(session):
    today = business_date()
    c = customer(session)
    invoice(session, customer=c, total="50000.00", status="paid",
            amount_paid="50000.00", due_date=today - dt.timedelta(days=90))
    invoice(session, customer=c, total="50000.00", status="cancelled",
            due_date=today - dt.timedelta(days=90))
    assert risk_detection.detect_risks(session, as_of=today) == []


def test_partially_paid_outstanding_still_counts(session):
    today = business_date()
    c = customer(session)
    invoice(session, customer=c, total="20000.00", amount_paid="19000.00",
            due_date=today - dt.timedelta(days=5))
    risks = risk_detection.detect_risks(session, as_of=today)
    # 1000 outstanding — below high-value threshold
    assert all(r["risk_category"] != "high_value_overdue" for r in risks)


def test_repeated_late_payments_rule(session):
    today = business_date()
    c = customer(session)
    for i in range(2):
        inv = invoice(
            session, customer=c, total="500.00", status="paid",
            amount_paid="500.00",
            issue_date=today - dt.timedelta(days=60 + i),
            due_date=today - dt.timedelta(days=60 + i),
        )
        payment(
            session, invoice=inv, amount="500.00",
            paid_at=_paid_at(today - dt.timedelta(days=59 + i)),  # 1 day late
        )
    # a voided late payment must not count
    inv_v = invoice(session, customer=c, total="500.00", status="confirmed",
                    due_date=today - dt.timedelta(days=10))
    payment(session, invoice=inv_v, amount="500.00", status="voided",
            paid_at=_paid_at(today))

    risks = risk_detection.detect_risks(session, as_of=today)
    late = [r for r in risks if r["risk_category"] == "repeated_late_payments"]
    assert len(late) == 1
    assert "2 posted payments" in late[0]["detection_reason"]


def test_renewal_unpaid_rule(session):
    today = business_date()
    c = customer(session)
    subscription(session, customer=c, next_billing_offset_days=10)
    invoice(session, customer=c, total="300.00", due_date=today - dt.timedelta(days=3))

    risks = risk_detection.detect_risks(session, as_of=today)
    renewal = [r for r in risks if r["risk_category"] == "renewal_unpaid"]
    assert len(renewal) == 1
    assert renewal[0]["subscription_id"] is not None


def test_renewal_unpaid_ignores_clean_accounts(session):
    today = business_date()
    c = customer(session)
    subscription(session, customer=c, next_billing_offset_days=10)
    invoice(session, customer=c, total="300.00", status="paid",
            amount_paid="300.00", due_date=today - dt.timedelta(days=3))

    risks = risk_detection.detect_risks(session, as_of=today)
    assert not [r for r in risks if r["risk_category"] == "renewal_unpaid"]


def test_large_exposure_rule(session):
    today = business_date()
    c = customer(session)
    # monthly recurring 100 → capacity gauge = 300; outstanding 2000 >> 300
    subscription(session, customer=c, items=(("1", "100.00"),), next_billing_offset_days=90)
    invoice(session, customer=c, total="2000.00", due_date=today + dt.timedelta(days=30))

    risks = risk_detection.detect_risks(session, as_of=today)
    exp = [r for r in risks if r["risk_category"] == "large_exposure"]
    assert len(exp) == 1
    assert exp[0]["outstanding_amount"] == Decimal("2000.00")


def test_severity_scoring_high(session):
    today = business_date()
    c = customer(session)
    invoice(session, customer=c, total="60000.00",
            due_date=today - dt.timedelta(days=90))
    risks = risk_detection.detect_risks(session, as_of=today)
    assert any(r["severity"] == "high" for r in risks)


def test_risk_summary_aggregates(session):
    today = business_date()
    c = customer(session)
    invoice(session, customer=c, total="15000.00", due_date=today - dt.timedelta(days=10))
    invoice(session, customer=c, total="100.00", due_date=today - dt.timedelta(days=3))

    risks = risk_detection.detect_risks(session, as_of=today)
    s = risk_detection.risk_summary(risks)
    assert s["total_risks"] == len(risks)
    assert s["customers_at_risk"] == 1
    assert s["total_outstanding_at_risk"] > 0
    assert set(s["by_severity"]) == {"high", "medium", "low"}


def test_risk_records_carry_required_fields(session):
    today = business_date()
    c = customer(session, name="Risk Corp")
    invoice(session, customer=c, total="15000.00", due_date=today - dt.timedelta(days=10))

    risks = risk_detection.detect_risks(session, as_of=today)
    r = next(x for x in risks if x["risk_category"] == "high_value_overdue")
    for field in (
        "customer_id", "customer_name", "outstanding_amount", "days_overdue",
        "risk_category", "severity", "detection_reason", "recommended_action",
        "risk_index",
    ):
        assert field in r
    assert r["customer_name"] == "Risk Corp"
