"""Pydantic v2 DTOs. Money fields are Decimal; FastAPI serializes them as
JSON numbers with fixed precision — frontend treats them as numbers/strings.
"""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Money leaves the API as a JSON number (float64 is exact for 2dp amounts at
# this scale); inputs stay Decimal so all math remains decimal-safe.
JSONDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]

InvoiceStatus = Literal["draft", "confirmed", "paid", "cancelled"]
PaymentMethod = Literal["upi", "bank_transfer", "cash", "card", "other"]
PaymentStatus = Literal["posted", "voided"]


# --- Invoices -----------------------------------------------------------------

class InvoiceCreateRequest(BaseModel):
    subscription_id: uuid.UUID
    period_start: dt.date | None = None  # default: subscription.next_billing_date
    period_end: dt.date | None = None    # default: period_start + frequency
    due_date: dt.date | None = None      # default: issue_date + 7 days


class InvoicePatchRequest(BaseModel):
    due_date: dt.date | None = None
    notes: str | None = None


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID | None
    subscription_line_id: uuid.UUID | None
    description: str
    position: int
    quantity: JSONDecimal
    unit_price: JSONDecimal
    subtotal: JSONDecimal
    tax_amount: JSONDecimal
    discount_amount: JSONDecimal
    line_total: JSONDecimal
    meta: dict | None


class InvoiceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    subscription_id: uuid.UUID | None
    customer_id: uuid.UUID
    customer_name: str | None = None  # enriched via P1 contract
    status: str
    issue_date: dt.date
    due_date: dt.date
    period_start: dt.date
    period_end: dt.date
    currency: str
    subtotal: JSONDecimal
    tax_total: JSONDecimal
    discount_total: JSONDecimal
    total_amount: JSONDecimal
    amount_paid: JSONDecimal
    outstanding: JSONDecimal


class InvoiceDetail(InvoiceSummary):
    notes: str | None
    last_emailed_at: dt.datetime | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    confirmed_at: dt.datetime | None
    cancelled_at: dt.datetime | None
    lines: list[InvoiceLineOut]
    payments: list["PaymentOut"]


class EmailRequest(BaseModel):
    to: str | None = None  # default: customer email
    subject: str | None = None
    message: str | None = None


class EmailResult(BaseModel):
    sent: bool
    emailed_at: dt.datetime | None = None
    reason: str | None = None


# --- Payments -----------------------------------------------------------------

class PaymentCreateRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    method: PaymentMethod
    paid_at: dt.datetime | None = None  # default: now
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=64)


class PaymentVoidRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_reference: str
    invoice_id: uuid.UUID
    amount: JSONDecimal
    method: str
    status: str
    paid_at: dt.datetime
    notes: str | None
    recorded_by: uuid.UUID | None
    voided_at: dt.datetime | None
    void_reason: str | None
    created_at: dt.datetime


InvoiceDetail.model_rebuild()


# --- Billing runs ---------------------------------------------------------------

class BillingRunRequest(BaseModel):
    run_for_date: dt.date | None = None  # default: today
    limit: int = Field(default=200, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class BillingRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trigger_source: str
    requested_by: uuid.UUID | None
    run_for_date: dt.date
    status: str
    scanned: int
    generated: int
    skipped: int
    failed: int
    errors: list | None
    started_at: dt.datetime
    finished_at: dt.datetime | None


class BillingRunResult(BillingRunOut):
    remaining: int  # due subscriptions still unprocessed after this run


class DueSubscriptionOut(BaseModel):
    subscription_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    billing_frequency: str
    next_billing_date: dt.date
    expiry_date: dt.date | None
    line_count: int


# --- Dashboard ------------------------------------------------------------------

class RecentPaymentOut(BaseModel):
    id: uuid.UUID
    payment_reference: str
    invoice_id: uuid.UUID
    invoice_number: str
    amount: JSONDecimal
    method: str
    paid_at: dt.datetime


class OverdueInvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer_name: str | None = None
    due_date: dt.date
    total_amount: JSONDecimal
    amount_paid: JSONDecimal
    outstanding: JSONDecimal
    days_overdue: int


class DashboardSummary(BaseModel):
    active_subscriptions: int
    revenue_received: JSONDecimal
    outstanding_amount: JSONDecimal
    overdue_count: int
    overdue_amount: JSONDecimal
    draft_count: int
    recent_payments: list[RecentPaymentOut]
    top_overdue: list[OverdueInvoiceOut]


class TrendPoint(BaseModel):
    period: str
    invoiced: JSONDecimal
    collected: JSONDecimal
    outstanding: JSONDecimal  # running balance at end of period


class RevenueTrendOut(BaseModel):
    interval: str
    points: list[TrendPoint]
