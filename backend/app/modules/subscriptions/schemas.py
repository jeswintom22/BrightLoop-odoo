"""P3 request/response schemas."""

import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class TemplateLineIn(BaseModel):
    product_id: int | None = None
    plan_id: int | None = None
    description: str = ""
    quantity: Decimal = Field(gt=0, default=Decimal("1"))


class TemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    validity_days: int = Field(default=15, ge=1, le=365)
    lines: list[TemplateLineIn] = Field(min_length=1)


class TemplateLineOut(TemplateLineIn):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    validity_days: int
    is_active: bool
    lines: list[TemplateLineOut] = []
    model_config = {"from_attributes": True}


class QuotationLineIn(BaseModel):
    product_id: int | None = None
    product_variant_id: int | None = None
    plan_id: int | None = None
    description: str = ""
    quantity: Decimal = Field(gt=0, default=Decimal("1"))


class QuotationCreateRequest(BaseModel):
    customer_id: uuid.UUID
    template_id: uuid.UUID | None = None
    lines: list[QuotationLineIn] | None = None
    notes: str | None = None


class QuotationLineOut(BaseModel):
    id: uuid.UUID
    product_id: int | None
    product_variant_id: int | None
    plan_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    line_total: Decimal
    model_config = {"from_attributes": True}


class QuotationOut(BaseModel):
    id: uuid.UUID
    quotation_number: str
    customer_id: uuid.UUID
    status: str
    issue_date: dt.date
    valid_until: dt.date
    subtotal: Decimal
    tax_total: Decimal
    discount_total: Decimal
    total_amount: Decimal
    notes: str | None
    lines: list[QuotationLineOut] = []
    model_config = {"from_attributes": True}


class ConvertRequest(BaseModel):
    start_date: dt.date | None = None
    payment_terms: str | None = None


class SubscriptionItemOut(BaseModel):
    id: uuid.UUID
    product_id: int | None
    product_variant_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    subscription_number: str
    customer_id: uuid.UUID
    plan_id: int | None
    quotation_id: uuid.UUID | None
    status: str
    billing_frequency: str
    start_date: dt.date | None
    expiry_date: dt.date | None
    next_billing_date: dt.date | None
    payment_terms: str | None
    items: list[SubscriptionItemOut] = []
    model_config = {"from_attributes": True}
