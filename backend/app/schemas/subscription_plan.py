import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator

ALLOWED_BILLING_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}
ALLOWED_PLAN_STATUSES = {"active", "inactive", "archived"}


class SubscriptionPlanBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Subscription plan name")
    description: Optional[str] = Field(None, description="Detailed plan description")
    product_id: int = Field(..., description="ID of associated parent product")
    product_variant_id: Optional[int] = Field(None, description="Optional ID of associated product variant")
    price: Decimal = Field(..., ge=0, description="Plan price per billing cycle (non-negative)")
    billing_frequency: str = Field(..., description="Billing frequency: daily, weekly, monthly, yearly")
    minimum_quantity: int = Field(1, ge=1, description="Minimum order quantity (at least 1)")
    available_from: date = Field(..., description="Date from which the plan becomes available")
    available_until: Optional[date] = Field(None, description="Date until which the plan is available")
    status: str = Field("active", description="Plan status: active, inactive, or archived")

    # Lifecycle Settings
    allow_pause: bool = Field(True, description="Whether subscribers can pause this plan")
    allow_renewal: bool = Field(True, description="Whether subscribers can renew this plan")
    allow_early_closure: bool = Field(True, description="Whether subscribers can close the plan early")
    automatic_closure: bool = Field(False, description="Whether plan auto-closes when availability ends")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Plan name is required and cannot be empty or whitespace only.")
        return trimmed

    @field_validator("billing_frequency")
    @classmethod
    def validate_billing_frequency(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ALLOWED_BILLING_FREQUENCIES:
            raise ValueError(
                f"Invalid billing frequency '{v}'. Must be one of: {', '.join(sorted(ALLOWED_BILLING_FREQUENCIES))}"
            )
        return normalized

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ALLOWED_PLAN_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(ALLOWED_PLAN_STATUSES))}"
            )
        return normalized

    @model_validator(mode="after")
    def validate_availability_dates(self):
        if self.available_until is not None and self.available_until < self.available_from:
            raise ValueError("available_until date cannot be before available_from date.")
        return self


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    product_id: Optional[int] = None
    product_variant_id: Optional[int] = None
    price: Optional[Decimal] = Field(None, ge=0)
    billing_frequency: Optional[str] = None
    minimum_quantity: Optional[int] = Field(None, ge=1)
    available_from: Optional[date] = None
    available_until: Optional[date] = None
    status: Optional[str] = None
    allow_pause: Optional[bool] = None
    allow_renewal: Optional[bool] = None
    allow_early_closure: Optional[bool] = None
    automatic_closure: Optional[bool] = None

    @field_validator("billing_frequency")
    @classmethod
    def validate_billing_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in ALLOWED_BILLING_FREQUENCIES:
                raise ValueError(
                    f"Invalid billing frequency '{v}'. Must be one of: {', '.join(sorted(ALLOWED_BILLING_FREQUENCIES))}"
                )
            return normalized
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().lower()
            if normalized not in ALLOWED_PLAN_STATUSES:
                raise ValueError(
                    f"Invalid status '{v}'. Must be one of: {', '.join(sorted(ALLOWED_PLAN_STATUSES))}"
                )
            return normalized
        return v

    @model_validator(mode="after")
    def validate_availability_dates(self):
        if self.available_from is not None and self.available_until is not None:
            if self.available_until < self.available_from:
                raise ValueError("available_until date cannot be before available_from date.")
        return self


class SubscriptionPlanStatusUpdate(BaseModel):
    status: str = Field(..., description="New status (active, inactive, archived)")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ALLOWED_PLAN_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(ALLOWED_PLAN_STATUSES))}"
            )
        return normalized


class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    product_name: Optional[str] = None
    variant_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanListResponse(BaseModel):
    items: List[SubscriptionPlanResponse]
    total: int
    page: int
    page_size: int
    pages: int
