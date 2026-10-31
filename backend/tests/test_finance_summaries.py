"""Financial summary generation — dedupe, regenerate, metrics correctness."""

import datetime as dt
from decimal import Decimal

import sqlalchemy as sa

from app.core.time import business_date
from app.modules.finance_intelligence import service
from app.modules.finance_intelligence.ai.provider import TemplateProvider
from app.modules.finance_intelligence.models import FinancialSummary

from finance_seed import customer, invoice, payment


def test_generate_summary_persists_with_metrics(session):
    today = business_date()
    c = customer(session)
    inv = invoice(session, customer=c, total="1000.00", issue_date=today)
    payment(session, invoice=inv, amount="1000.00")

    row, created = service.generate_summary(
        session,
        llm=TemplateProvider(),
        period_kind="month",
        period_start=dt.date(today.year, today.month, 1),
        period_end=today,
        generated_by=None,
    )
    assert created is True
    assert row.id is not None
    assert row.provider == "template"
    assert "PERFORMANCE" in row.summary_text
    assert row.metrics["current"]["collected"] == 1000.0
    assert row.metrics["range"]["from"] == dt.date(today.year, today.month, 1).isoformat()


def test_duplicate_period_returns_existing(session):
    today = business_date()
    start = dt.date(today.year, today.month, 1)

    r1, c1 = service.generate_summary(
        session, llm=TemplateProvider(), period_kind="month",
        period_start=start, period_end=today,
    )
    r2, c2 = service.generate_summary(
        session, llm=TemplateProvider(), period_kind="month",
        period_start=start, period_end=today,
    )
    assert c1 is True and c2 is False
    assert r1.id == r2.id
    count = session.scalar(sa.select(sa.func.count(FinancialSummary.id)))
    assert count == 1


def test_regenerate_updates_in_place(session):
    today = business_date()
    start = dt.date(today.year, today.month, 1)
    r1, _ = service.generate_summary(
        session, llm=TemplateProvider(), period_kind="month",
        period_start=start, period_end=today,
    )
    r2, created = service.generate_summary(
        session, llm=TemplateProvider(), period_kind="month",
        period_start=start, period_end=today, regenerate=True,
    )
    assert created is True
    assert r2.id == r1.id
    count = session.scalar(sa.select(sa.func.count(FinancialSummary.id)))
    assert count == 1


def test_summary_defaults_to_current_month(session):
    row, _ = service.generate_summary(session, llm=TemplateProvider())
    today = business_date()
    assert row.period_start == dt.date(today.year, today.month, 1)
    assert row.period_end == today
    assert row.period_kind == "month"


def test_summary_metrics_reflect_period_not_all_time(session):
    """Invoices outside the window must not leak into the report."""
    today = business_date()
    c = customer(session)
    old = invoice(session, customer=c, total="9999.00",
                  issue_date=today - dt.timedelta(days=200))
    payment(
        session, invoice=old, amount="9999.00",
        paid_at=dt.datetime.combine(today - dt.timedelta(days=200), dt.time(10), tzinfo=dt.timezone.utc),
    )
    inv = invoice(session, customer=c, total="500.00", issue_date=today)
    payment(session, invoice=inv, amount="500.00")

    row, _ = service.generate_summary(
        session, llm=TemplateProvider(), period_kind="custom",
        period_start=today - dt.timedelta(days=7), period_end=today,
    )
    assert row.metrics["current"]["invoiced"] == 500.0
    assert row.metrics["current"]["collected"] == 500.0
    assert row.metrics["previous"]["collected"] == 0.0
