"""Financial summary orchestration — metrics assembly, dedupe, persistence."""

import datetime as dt
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ...core.time import business_date
from .analytics import reports
from .ai import summarizer
from .ai.provider import LLMProvider
from .models import FinancialSummary


def _default_period() -> tuple[str, dt.date, dt.date]:
    today = business_date()
    return "month", dt.date(today.year, today.month, 1), today


def _json_safe(obj):
    """Persisted metrics must be plain JSON types — Decimal→float,
    date/datetime→ISO str, UUID→str. Stored metrics are informational;
    the database remains the source of truth."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


def generate_summary(
    session: Session,
    *,
    llm: LLMProvider,
    period_kind: str = "month",
    period_start: dt.date | None = None,
    period_end: dt.date | None = None,
    regenerate: bool = False,
    generated_by: uuid.UUID | None = None,
) -> tuple[FinancialSummary, bool]:
    """Returns (summary, created). Existing report for the same period is
    returned unless ``regenerate`` — avoids duplicate AI reports."""
    if period_start is None or period_end is None:
        _, def_start, def_end = _default_period()
        period_start = period_start or def_start
        period_end = period_end or def_end
    if period_end < period_start:
        period_start, period_end = period_end, period_start

    existing = session.scalar(
        sa.select(FinancialSummary).where(
            FinancialSummary.period_kind == period_kind,
            FinancialSummary.period_start == period_start,
            FinancialSummary.period_end == period_end,
        )
    )
    if existing is not None and not regenerate:
        return existing, False

    metrics = _json_safe(
        reports.performance_report(
            session, date_from=period_start, date_to=period_end
        )
    )
    rendered = summarizer.generate_summary(llm, metrics)

    if existing is not None:
        existing.metrics = metrics
        existing.summary_text = rendered["summary_text"]
        existing.provider = rendered["provider"]
        existing.model = rendered["model"]
        existing.generated_by = generated_by
        session.flush()
        return existing, True

    row = FinancialSummary(
        period_kind=period_kind,
        period_start=period_start,
        period_end=period_end,
        metrics=metrics,
        summary_text=rendered["summary_text"],
        provider=rendered["provider"],
        model=rendered["model"],
        generated_by=generated_by,
    )
    session.add(row)
    session.flush()
    return row, True
