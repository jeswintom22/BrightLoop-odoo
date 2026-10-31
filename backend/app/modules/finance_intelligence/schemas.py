"""Pydantic v2 DTOs for the finance-intelligence API."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

JSONDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]


# --- Revenue analytics ---------------------------------------------------------


class MrrPlanRow(BaseModel):
    plan: str
    mrr: JSONDecimal


class MrrFrequencyRow(BaseModel):
    frequency: str
    mrr: JSONDecimal


class MrrSnapshotOut(BaseModel):
    as_of: str
    subscription_count: int
    mrr: JSONDecimal
    arr: JSONDecimal
    by_plan: list[MrrPlanRow]
    by_frequency: list[MrrFrequencyRow]


class MrrTrendPoint(BaseModel):
    period: str
    as_of: str
    mrr: JSONDecimal
    arr: JSONDecimal


class MrrTrendOut(BaseModel):
    points: list[MrrTrendPoint]


class RevenuePoint(BaseModel):
    period: str
    invoiced: JSONDecimal
    collected: JSONDecimal


class DateRange(BaseModel):
    from_: dt.date = Field(alias="from")
    to: dt.date

    model_config = ConfigDict(populate_by_name=True)


class GrowthPct(BaseModel):
    invoiced: JSONDecimal | None
    collected: JSONDecimal | None


class RevenueTotals(BaseModel):
    invoiced: JSONDecimal
    collected: JSONDecimal


class RevenueTrendsOut(BaseModel):
    interval: str
    range: DateRange
    previous_range: DateRange
    totals: RevenueTotals
    previous_totals: RevenueTotals
    growth_pct: GrowthPct
    points: list[RevenuePoint]


class BreakdownRow(BaseModel):
    key: str
    amount: JSONDecimal
    share_pct: JSONDecimal


class BreakdownOut(BaseModel):
    by: str
    range: DateRange
    rows: list[BreakdownRow]


class UpcomingBilling(BaseModel):
    subscription_id: str
    subscription_number: str
    customer_id: str
    next_billing_date: str
    billing_frequency: str
    expected_amount: JSONDecimal


class DueReceivable(BaseModel):
    invoice_id: str
    invoice_number: str
    customer_id: str
    customer_name: str | None
    due_date: str
    outstanding: JSONDecimal
    days_overdue: int


class ForecastOut(BaseModel):
    as_of: str
    horizon_days: int
    horizon_end: str
    collection_rate: JSONDecimal
    collection_rate_window_days: int
    expected_billings: JSONDecimal
    expected_billings_count: int
    outstanding_due: JSONDecimal
    expected_collections: JSONDecimal
    expected_total_cash_in: JSONDecimal
    upcoming_billings: list[UpcomingBilling]
    due_receivables: list[DueReceivable]


class PerformanceReportOut(BaseModel):
    range: DateRange
    previous_range: DateRange
    current: dict
    previous: dict
    growth_pct: GrowthPct
    collection_rate: JSONDecimal | None
    mrr: JSONDecimal
    arr: JSONDecimal
    active_subscriptions_in_mrr: int
    plan_revenue: list[BreakdownRow]


# --- Risk intelligence ----------------------------------------------------------

RiskCategory = Literal[
    "high_value_overdue",
    "multiple_overdue",
    "repeated_late_payments",
    "renewal_unpaid",
    "large_exposure",
]
RiskSeverity = Literal["high", "medium", "low"]


class RiskRecord(BaseModel):
    risk_index: int
    customer_id: uuid.UUID | None
    customer_name: str | None
    subscription_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    invoice_number: str | None
    outstanding_amount: JSONDecimal
    days_overdue: int
    risk_category: str
    severity: str
    detection_reason: str
    recommended_action: str


class RiskSummaryOut(BaseModel):
    total_risks: int
    customers_at_risk: int
    total_outstanding_at_risk: JSONDecimal
    by_severity: dict
    by_category: dict


class RiskListOut(BaseModel):
    as_of: dt.date
    summary: RiskSummaryOut
    risks: list[RiskRecord]


class RiskExplainRequest(BaseModel):
    """Reference a risk by index (from GET /risks) or supply the record."""

    risk_index: int | None = None
    risk: RiskRecord | None = None


class RiskExplanationOut(BaseModel):
    explanation: str
    provider: str
    model: str | None
    risk: RiskRecord


# --- Copilot --------------------------------------------------------------------


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class CopilotResponse(BaseModel):
    answer: str
    intent: str
    provider: str
    model: str | None
    metrics: dict
    sources: list[str]
    range: dict


# --- Financial summaries ----------------------------------------------------------


class SummaryGenerateRequest(BaseModel):
    period_kind: Literal["month", "custom"] = "custom"
    period_start: dt.date | None = None  # default: 1st of current month
    period_end: dt.date | None = None    # default: today
    regenerate: bool = False


class FinancialSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_kind: str
    period_start: dt.date
    period_end: dt.date
    metrics: dict
    summary_text: str
    provider: str
    model: str | None
    generated_by: uuid.UUID | None
    created_at: dt.datetime
