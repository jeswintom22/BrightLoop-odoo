from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from .models import LifecycleStatus, BillingFrequency


class LifecycleAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    CLOSE = "close"


# ==========================================
# Quotation Line Schemas
# ==========================================

class QuotationLineBase(BaseModel):
    product_id: Optional[str] = Field(None, description="Product identifier or SKU")
    product_name: str = Field(..., min_length=1, description="Product name")
    description: Optional[str] = Field(None, description="Line item description")
    quantity: float = Field(default=1.0, gt=0, description="Quantity ordered")
    unit_price: float = Field(..., ge=0, description="Unit price before discounts and taxes")
    discount_percent: float = Field(default=0.0, ge=0, le=100, description="Discount percentage (0-100)")
    tax_percent: float = Field(default=0.0, ge=0, description="Tax percentage")
    billing_frequency: str = Field(
        default="monthly",
        description="Billing frequency (daily, weekly, monthly, yearly)"
    )

    @field_validator("billing_frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        cleaned = v.strip().lower()
        valid = {"daily", "weekly", "monthly", "yearly"}
        if cleaned not in valid:
            raise ValueError(f"billing_frequency must be one of {valid}")
        return cleaned


class QuotationLineCreate(QuotationLineBase):
    pass


class QuotationLineRead(QuotationLineBase):
    id: int
    quotation_id: int
    subtotal: float

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Quotation Schemas
# ==========================================

class QuotationCreate(BaseModel):
    quotation_number: Optional[str] = Field(
        None,
        description="Optional explicit quotation number; auto-generated (e.g., QUO-2026-0001) if omitted"
    )
    customer_id: str = Field(..., min_length=1, description="Customer or User ID")
    customer_name: str = Field(..., min_length=1, description="Customer full name")
    customer_email: EmailStr = Field(..., description="Customer email address")
    valid_until: date = Field(..., description="Quotation validity expiration date")
    template_name: Optional[str] = Field(None, description="Quotation template or offer name")
    notes: Optional[str] = Field(None, description="Terms or special notes")
    currency: str = Field(default="USD", max_length=10, description="ISO currency code")
    status: Optional[LifecycleStatus] = Field(
        default=LifecycleStatus.DRAFT,
        description="Initial status (Draft or Quotation)"
    )
    lines: List[QuotationLineCreate] = Field(
        ...,
        min_length=1,
        description="List of product lines included in quotation"
    )


class QuotationStatusUpdate(BaseModel):
    status: LifecycleStatus = Field(..., description="New lifecycle status for quotation")


class QuotationRead(BaseModel):
    id: int
    quotation_number: str
    customer_id: str
    customer_name: str
    customer_email: str
    valid_until: date
    status: LifecycleStatus
    total_amount: float
    currency: str
    template_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    lines: List[QuotationLineRead] = []

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Subscription Schemas
# ==========================================

class SubscriptionConvertRequest(BaseModel):
    start_date: Optional[date] = Field(
        None,
        description="Subscription activation date. Defaults to today."
    )
    billing_frequency: Optional[str] = Field(
        None,
        description="Optional billing frequency override (daily, weekly, monthly, yearly)"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional subscription notes"
    )
    auto_confirm: Optional[bool] = Field(
        False,
        description="Automatically promote quotation to Confirmed if still in Draft/Quotation"
    )

    @field_validator("billing_frequency")
    @classmethod
    def validate_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        valid = {"daily", "weekly", "monthly", "yearly"}
        if cleaned not in valid:
            raise ValueError(f"billing_frequency must be one of {valid}")
        return cleaned


class SubscriptionLifecycleUpdate(BaseModel):
    action: LifecycleAction = Field(..., description="Action to perform: 'pause', 'resume', or 'close'")
    reason: Optional[str] = Field(None, description="Optional explanation or reason for the state change")


class SubscriptionLineRead(BaseModel):
    id: int
    subscription_id: int
    product_id: Optional[str] = None
    product_name: str
    description: Optional[str] = None
    quantity: float
    unit_price: float
    discount_percent: float
    tax_percent: float
    subtotal: float
    billing_frequency: str

    model_config = ConfigDict(from_attributes=True)


class SubscriptionRead(BaseModel):
    id: int
    subscription_number: str
    quotation_id: Optional[int] = None
    customer_id: str
    customer_name: str
    customer_email: str
    status: LifecycleStatus
    start_date: date
    end_date: Optional[date] = None
    next_billing_date: Optional[date] = None
    billing_frequency: str
    total_amount: float
    currency: str
    pause_reason: Optional[str] = None
    close_reason: Optional[str] = None
    paused_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    lines: List[SubscriptionLineRead] = []

    model_config = ConfigDict(from_attributes=True)
