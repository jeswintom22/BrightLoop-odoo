"""Schemas for P2 tax configurations and discounts (admin-managed)."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# --- Tax configurations -------------------------------------------------------


class TaxBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    tax_percentage: Decimal = Field(..., ge=0, le=100)
    is_active: bool = True


class TaxCreate(TaxBase):
    pass


class TaxUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tax_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class TaxResponse(TaxBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --- Discounts -----------------------------------------------------------------

ALLOWED_DISCOUNT_TYPES = {"fixed_amount", "percentage"}


class DiscountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    discount_type: str = Field(..., description="fixed_amount | percentage")
    discount_value: Decimal = Field(..., ge=0)
    start_date: datetime
    expiry_date: Optional[datetime] = None
    min_purchase_amount: Decimal = Field(Decimal("0"), ge=0)
    min_quantity: Decimal = Field(Decimal("0"), ge=0)
    usage_limit: Optional[int] = Field(None, ge=1)
    is_active: bool = True
    product_ids: List[int] = Field(
        default_factory=list,
        description="Products this discount applies to (empty = none)",
    )

    @field_validator("discount_type")
    @classmethod
    def _type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_DISCOUNT_TYPES:
            raise ValueError(
                f"Invalid discount_type '{v}'. Allowed: {sorted(ALLOWED_DISCOUNT_TYPES)}"
            )
        return v

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def _rules(self):
        if self.expiry_date is not None and self.expiry_date < self.start_date:
            raise ValueError("expiry_date cannot be before start_date")
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        return self


class DiscountCreate(DiscountBase):
    pass


class DiscountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = Field(None, ge=0)
    start_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    min_purchase_amount: Optional[Decimal] = Field(None, ge=0)
    min_quantity: Optional[Decimal] = Field(None, ge=0)
    usage_limit: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    product_ids: Optional[List[int]] = None

    @field_validator("discount_type")
    @classmethod
    def _type(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ALLOWED_DISCOUNT_TYPES:
            raise ValueError(f"Invalid discount_type '{v}'")
        return v


class DiscountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    discount_type: str
    discount_value: Decimal
    start_date: datetime
    expiry_date: Optional[datetime]
    min_purchase_amount: Decimal
    min_quantity: Decimal = Decimal("0")
    usage_limit: Optional[int]
    usage_count: int
    is_active: bool
    product_ids: List[int] = []


class DiscountListResponse(BaseModel):
    items: List[DiscountResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TaxListResponse(BaseModel):
    items: List[TaxResponse]
    total: int
    page: int
    page_size: int
    pages: int
