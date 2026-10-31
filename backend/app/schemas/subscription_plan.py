from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

ALLOWED_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}
ALLOWED_PLAN_STATUSES = {"draft", "active", "archived"}


class SubscriptionPlanBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    product_id: int = Field(..., description="Parent product")
    product_variant_id: Optional[int] = None
    tax_id: Optional[int] = None
    price: Decimal = Field(..., ge=0, description="Recurring plan price")
    billing_frequency: str = Field(..., description="daily|weekly|monthly|yearly")
    minimum_quantity: int = Field(1, ge=1)
    start_date: date
    end_date: Optional[date] = None
    status: str = Field("active")
    allow_pause: bool = True
    allow_renewal: bool = True
    allow_early_closure: bool = True
    auto_closure: bool = False

    @field_validator("billing_frequency")
    @classmethod
    def _freq(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_FREQUENCIES:
            raise ValueError(
                f"Invalid billing_frequency '{v}'. Allowed: {sorted(ALLOWED_FREQUENCIES)}"
            )
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_PLAN_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Allowed: {sorted(ALLOWED_PLAN_STATUSES)}"
            )
        return v

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    product_variant_id: Optional[int] = None
    tax_id: Optional[int] = None
    price: Optional[Decimal] = Field(None, ge=0)
    billing_frequency: Optional[str] = None
    minimum_quantity: Optional[int] = Field(None, ge=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    allow_pause: Optional[bool] = None
    allow_renewal: Optional[bool] = None
    allow_early_closure: Optional[bool] = None
    auto_closure: Optional[bool] = None

    @field_validator("billing_frequency")
    @classmethod
    def _freq(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ALLOWED_FREQUENCIES:
            raise ValueError(f"Invalid billing_frequency '{v}'")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ALLOWED_PLAN_STATUSES:
            raise ValueError(f"Invalid status '{v}'")
        return v


class SubscriptionPlanResponse(SubscriptionPlanBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SubscriptionPlanListResponse(BaseModel):
    items: List[SubscriptionPlanResponse]
    total: int
    page: int
    page_size: int
    pages: int
