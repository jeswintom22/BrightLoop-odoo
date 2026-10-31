"""Finance-intelligence API — all endpoints admin/staff only.

Customer-role tokens are rejected by require_roles; AI endpoints are
additionally rate-limited per user (AI_RATE_LIMIT_PER_MINUTE).
"""

import datetime as dt
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.pagination import Page, paginate
from ...core.time import business_date
from ...deps import (
    CurrentUser,
    get_db,
    get_llm_provider,
    get_product_analytics_provider,
    get_rate_limiter,
    get_subscription_analytics_provider,
    require_roles,
)
from . import service
from .ai import copilot, risk_explainer
from .ai.provider import LLMProvider, RateLimiter
from .analytics import forecasting, mrr_arr, revenue, risk_detection
from .contracts import ProductAnalyticsProvider, SubscriptionAnalyticsProvider
from .models import FinancialSummary
from .schemas import (
    BreakdownOut,
    CopilotRequest,
    CopilotResponse,
    FinancialSummaryOut,
    ForecastOut,
    MrrSnapshotOut,
    MrrTrendOut,
    PerformanceReportOut,
    RevenueTrendsOut,
    RiskExplainRequest,
    RiskExplanationOut,
    RiskListOut,
    RiskSummaryOut,
    SummaryGenerateRequest,
)

router = APIRouter(prefix="/finance-intelligence", tags=["finance-intelligence"])

READ = Depends(require_roles("admin", "staff"))


def _rate_check(limiter: RateLimiter, user: CurrentUser) -> None:
    if not limiter.allow(str(user.id)):
        raise AppError(
            "RATE_LIMITED",
            "Too many AI requests — wait a minute and retry",
            429,
        )


# --- Revenue analytics ----------------------------------------------------------


@router.get("/revenue/mrr", response_model=MrrSnapshotOut)
def get_mrr(
    as_of: dt.date | None = None,
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    return mrr_arr.mrr_snapshot(session, as_of or business_date())


@router.get("/revenue/arr", response_model=MrrSnapshotOut)
def get_arr(
    as_of: dt.date | None = None,
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    # ARR is derived from the same normalized snapshot (arr = mrr × 12).
    return mrr_arr.mrr_snapshot(session, as_of or business_date())


@router.get("/revenue/mrr-trend", response_model=MrrTrendOut)
def get_mrr_trend(
    date_from: dt.date = Query(alias="from"),
    date_to: dt.date = Query(alias="to"),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    return {"points": mrr_arr.mrr_trend(session, date_from, date_to)}


@router.get("/revenue/trends", response_model=RevenueTrendsOut)
def get_revenue_trends(
    interval: str = Query("month", pattern="^(day|week|month|year)$"),
    date_from: dt.date = Query(alias="from"),
    date_to: dt.date = Query(alias="to"),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    return revenue.revenue_trends(
        session, interval=interval, date_from=date_from, date_to=date_to
    )


@router.get("/revenue/breakdown", response_model=BreakdownOut)
def get_revenue_breakdown(
    by: str = Query("plan", pattern="^(plan|product|customer|period|payment_method)$"),
    date_from: dt.date = Query(alias="from"),
    date_to: dt.date = Query(alias="to"),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    return {
        "by": by,
        "range": {"from": date_from, "to": date_to},
        "rows": revenue.breakdown(
            session, by=by, date_from=date_from, date_to=date_to, limit=limit
        ),
    }


@router.get("/revenue/forecast", response_model=ForecastOut)
def get_forecast(
    horizon_days: int = Query(30, ge=1, le=180),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    return forecasting.forecast(session, horizon_days=horizon_days)


@router.get("/reports/performance", response_model=PerformanceReportOut)
def get_performance_report(
    date_from: dt.date = Query(alias="from"),
    date_to: dt.date = Query(alias="to"),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    from .analytics import reports

    return reports.performance_report(session, date_from=date_from, date_to=date_to)


# --- Risk intelligence ------------------------------------------------------------


def _filtered_risks(
    session: Session, severity: str | None, category: str | None
) -> tuple[dt.date, list[dict]]:
    today = business_date()
    risks = risk_detection.detect_risks(session, as_of=today)
    if severity:
        risks = [r for r in risks if r["severity"] == severity]
    if category:
        risks = [r for r in risks if r["risk_category"] == category]
    return today, risks


@router.get("/risks", response_model=RiskListOut)
def list_risks(
    severity: str | None = Query(None, pattern="^(high|medium|low)$"),
    category: str | None = Query(
        None,
        pattern="^(high_value_overdue|multiple_overdue|repeated_late_payments|renewal_unpaid|large_exposure)$",
    ),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    today, risks = _filtered_risks(session, severity, category)
    return {
        "as_of": today,
        "summary": risk_detection.risk_summary(risks),
        "risks": risks,
    }


@router.get("/risks/summary", response_model=RiskSummaryOut)
def get_risk_summary(
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    risks = risk_detection.detect_risks(session, as_of=business_date())
    return risk_detection.risk_summary(risks)


@router.post("/risks/explain", response_model=RiskExplanationOut)
def explain_risk(
    body: RiskExplainRequest,
    session: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
    limiter: RateLimiter = Depends(get_rate_limiter),
    user: CurrentUser = READ,
):
    _rate_check(limiter, user)
    if body.risk is not None:
        record = body.risk.model_dump()
    elif body.risk_index is not None:
        risks = risk_detection.detect_risks(session, as_of=business_date())
        match = next(
            (r for r in risks if r["risk_index"] == body.risk_index), None
        )
        if match is None:
            raise AppError("NOT_FOUND", "No risk with that index", 404)
        record = match
    else:
        raise AppError(
            "VALIDATION", "Provide risk_index or an inline risk record", 400
        )
    return risk_explainer.explain_risk(llm, record)


# --- Copilot ---------------------------------------------------------------------


@router.post("/copilot", response_model=CopilotResponse)
def ask_copilot(
    body: CopilotRequest,
    session: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
    product_analytics: ProductAnalyticsProvider = Depends(get_product_analytics_provider),
    subscription_analytics: SubscriptionAnalyticsProvider = Depends(
        get_subscription_analytics_provider
    ),
    limiter: RateLimiter = Depends(get_rate_limiter),
    user: CurrentUser = READ,
):
    _rate_check(limiter, user)
    return copilot.answer_question(
        session,
        question=body.question,
        llm=llm,
        product_analytics=product_analytics,
        subscription_analytics=subscription_analytics,
    )


# --- Financial summaries -----------------------------------------------------------


@router.get("/summaries", response_model=Page[FinancialSummaryOut])
def list_summaries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    stmt = sa.select(FinancialSummary).order_by(FinancialSummary.created_at.desc())
    items, total = paginate(session, stmt, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/summaries/generate",
    response_model=FinancialSummaryOut,
    status_code=status.HTTP_200_OK,
)
def generate_financial_summary(
    body: SummaryGenerateRequest,
    session: Session = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
    limiter: RateLimiter = Depends(get_rate_limiter),
    user: CurrentUser = READ,
):
    _rate_check(limiter, user)
    row, created = service.generate_summary(
        session,
        llm=llm,
        period_kind=body.period_kind,
        period_start=body.period_start,
        period_end=body.period_end,
        regenerate=body.regenerate,
        generated_by=user.id,
    )
    session.commit()
    return row


@router.get("/summaries/{summary_id}", response_model=FinancialSummaryOut)
def get_summary(
    summary_id: uuid.UUID,
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    row = session.get(FinancialSummary, summary_id)
    if row is None:
        raise AppError("NOT_FOUND", "Summary not found", 404)
    return row
