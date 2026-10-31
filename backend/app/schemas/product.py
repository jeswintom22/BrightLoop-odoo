from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.schemas.product_variant import ProductVariantBase, ProductVariantResponse

ALLOWED_PRODUCT_TYPES = {"goods", "service", "digital", "subscription"}


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    product_type: str = Field(..., description="Product type (goods, service, digital, subscription)")
    sales_price: Decimal = Field(..., ge=0, description="Sales price (non-negative)")
    cost_price: Decimal = Field(..., ge=0, description="Cost price (non-negative)")
    notes: Optional[str] = Field(None, description="Optional internal notes")
    tax_id: Optional[int] = Field(None, description="Associated tax configuration ID")
    is_active: bool = Field(True, description="Active status")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Product name is required and cannot be blank.")
        return trimmed

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v: str) -> str:
        lower_v = v.strip().lower()
        if lower_v not in ALLOWED_PRODUCT_TYPES:
            raise ValueError(
                f"Invalid product type '{v}'. Allowed types are: {', '.join(sorted(ALLOWED_PRODUCT_TYPES))}"
            )
        return lower_v


class ProductCreate(ProductBase):
    variants: Optional[List[ProductVariantBase]] = Field(
        default=None,
        description="Optional initial variants to create with this product"
    )


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_type: Optional[str] = None
    sales_price: Optional[Decimal] = Field(None, ge=0)
    cost_price: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    tax_id: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Product name cannot be blank.")
            return trimmed
        return v

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            lower_v = v.strip().lower()
            if lower_v not in ALLOWED_PRODUCT_TYPES:
                raise ValueError(
                    f"Invalid product type '{v}'. Allowed types are: {', '.join(sorted(ALLOWED_PRODUCT_TYPES))}"
                )
            return lower_v
        return v


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    variants: List[ProductVariantResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    pages: int
