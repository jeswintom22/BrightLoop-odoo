import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class TaxBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tax name (e.g. GST 18%, State VAT)")
    tax_percentage: Decimal = Field(..., ge=0, le=100, description="Tax rate percentage (0.00 to 100.00)")
    description: Optional[str] = Field(None, description="Optional description of the tax rule")
    is_active: bool = Field(True, description="Whether this tax configuration is currently active")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Tax name is required and cannot be empty or whitespace only.")
        return trimmed

    @field_validator("tax_percentage")
    @classmethod
    def validate_tax_percentage(cls, v: Decimal) -> Decimal:
        if v < Decimal("0.00") or v > Decimal("100.00"):
            raise ValueError("Tax percentage must be between 0.00% and 100.00%.")
        return v


class TaxCreate(TaxBase):
    pass


class TaxUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tax_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Tax name cannot be blank.")
            return trimmed
        return v


class TaxStatusUpdate(BaseModel):
    is_active: bool = Field(..., description="Active/inactive status flag")


class TaxResponse(TaxBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaxCalculationRequest(BaseModel):
    taxable_amount: Decimal = Field(..., ge=0, description="Eligible taxable amount (must be non-negative)")
    tax_id: Optional[uuid.UUID] = Field(None, description="UUID of existing tax configuration")
    tax_percentage: Optional[Decimal] = Field(None, ge=0, le=100, description="Explicit tax percentage to calculate against")

    @model_validator(mode="after")
    def validate_tax_input(self):
        if self.tax_id is None and self.tax_percentage is None:
            raise ValueError("Either 'tax_id' or 'tax_percentage' must be provided for tax calculation.")
        return self


class TaxCalculationResponse(BaseModel):
    taxable_amount: Decimal = Field(..., description="Initial taxable amount")
    tax_percentage: Decimal = Field(..., description="Applied tax rate percentage")
    tax_amount: Decimal = Field(..., description="Calculated tax amount rounded to 2 decimal places")
    final_amount: Decimal = Field(..., description="Final gross amount including tax (taxable_amount + tax_amount)")
    tax_name: Optional[str] = Field(None, description="Name of applied tax rule (if calculated via tax_id)")
    is_active: bool = Field(True, description="Status of the tax rule")
