"""
Pydantic v2 schemas for Discount management.
Covers CRUD, status toggle, code validation and application.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Shared / reusable
# ---------------------------------------------------------------------------

VALID_DISCOUNT_TYPES = {"fixed", "percentage"}


class DiscountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    discount_type: str = Field(..., description="'fixed' or 'percentage'")
    discount_value: Decimal = Field(..., gt=0, description="Must be > 0")
    start_date: datetime
    expiry_date: Optional[datetime] = None
    minimum_purchase_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    usage_limit: Optional[int] = Field(None, gt=0)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def code_must_be_uppercase(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Discount code cannot be empty or whitespace.")
        return v.upper()

    @field_validator("discount_type")
    @classmethod
    def discount_type_must_be_valid(cls, v: str) -> str:
        if v not in VALID_DISCOUNT_TYPES:
            raise ValueError(f"discount_type must be one of: {sorted(VALID_DISCOUNT_TYPES)}")
        return v

    @model_validator(mode="after")
    def validate_percentage_cap(self) -> "DiscountBase":
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100%.")
        return self

    @model_validator(mode="after")
    def validate_date_range(self) -> "DiscountBase":
        if self.expiry_date and self.expiry_date <= self.start_date:
            raise ValueError("expiry_date must be after start_date.")
        return self


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class DiscountCreate(DiscountBase):
    """Request body for POST /api/discounts."""
    applicable_product_ids: List[int] = Field(
        default_factory=list,
        description="Product IDs this discount applies to. Empty = all products.",
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class DiscountUpdate(BaseModel):
    """Request body for PUT /api/discounts/{discount_id}. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    minimum_purchase_amount: Optional[Decimal] = Field(None, ge=0)
    usage_limit: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    applicable_product_ids: Optional[List[int]] = None

    @field_validator("code")
    @classmethod
    def code_must_be_uppercase(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().upper()
            if not v:
                raise ValueError("Discount code cannot be empty or whitespace.")
        return v

    @field_validator("discount_type")
    @classmethod
    def discount_type_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_DISCOUNT_TYPES:
            raise ValueError(f"discount_type must be one of: {sorted(VALID_DISCOUNT_TYPES)}")
        return v


# ---------------------------------------------------------------------------
# Status toggle
# ---------------------------------------------------------------------------

class DiscountStatusUpdate(BaseModel):
    is_active: bool


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ApplicableProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class DiscountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    description: Optional[str]
    discount_type: str
    discount_value: Decimal
    start_date: datetime
    expiry_date: Optional[datetime]
    minimum_purchase_amount: Decimal
    usage_limit: Optional[int]
    usage_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    applicable_products: List[ApplicableProductSummary] = []


class DiscountListResponse(BaseModel):
    """Paginated list response."""
    items: List[DiscountResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Validate / Apply (discount code application)
# ---------------------------------------------------------------------------

class DiscountValidateRequest(BaseModel):
    """Dry-run: check if the code is applicable — does NOT increment usage_count."""
    code: str = Field(..., min_length=1)
    purchase_amount: Decimal = Field(..., gt=0, description="Cart / order amount before discount")
    product_id: Optional[int] = Field(
        None, description="If provided, validates product-level applicability too."
    )

    @field_validator("code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().upper()


class DiscountApplyRequest(DiscountValidateRequest):
    """Same as validate but increments usage_count atomically."""
    pass


class DiscountValidateResponse(BaseModel):
    """Returned by both /validate and /apply."""
    is_valid: bool
    discount_amount: Decimal
    final_amount: Decimal
    message: str
    discount: Optional[DiscountResponse] = None
