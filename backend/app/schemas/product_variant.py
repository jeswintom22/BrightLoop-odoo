from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ProductVariantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Variant name (e.g. 128GB Red, Brand X)")
    sku: Optional[str] = Field(None, max_length=100, description="Unique stock keeping unit")
    sales_price: Decimal = Field(..., ge=0, description="Variant sales price (must be non-negative)")
    cost_price: Decimal = Field(..., ge=0, description="Variant cost price (must be non-negative)")
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Configuration metadata (color, brand, specs)")
    is_active: bool = Field(True, description="Active status")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Variant name cannot be empty or whitespace only.")
        return trimmed


class ProductVariantCreate(ProductVariantBase):
    product_id: Optional[int] = Field(None, description="Parent product ID (optional if specified in path)")


class ProductVariantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, max_length=100)
    sales_price: Optional[Decimal] = Field(None, ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Variant name cannot be empty or whitespace only.")
            return trimmed
        return v


class ProductVariantResponse(ProductVariantBase):
    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
