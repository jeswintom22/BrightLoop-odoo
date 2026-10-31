import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.tax import TaxConfiguration
from app.schemas.tax import (
    TaxCreate,
    TaxUpdate,
    TaxCalculationRequest,
    TaxCalculationResponse,
)

TWO_PLACES = Decimal("0.01")


class TaxService:
    @staticmethod
    def get_taxes(db: Session, is_active: Optional[bool] = None) -> List[TaxConfiguration]:
        """Fetch all tax configurations, optionally filtered by active status."""
        query = select(TaxConfiguration).order_by(TaxConfiguration.name.asc())
        if is_active is not None:
            query = query.where(TaxConfiguration.is_active == is_active)
        return list(db.scalars(query).all())

    @staticmethod
    def get_tax_by_id(db: Session, tax_id: uuid.UUID) -> Optional[TaxConfiguration]:
        """Retrieve a specific tax configuration by its UUID."""
        return db.get(TaxConfiguration, tax_id)

    @staticmethod
    def create_tax(db: Session, tax_in: TaxCreate) -> TaxConfiguration:
        """Create a new tax configuration."""
        tax = TaxConfiguration(
            name=tax_in.name,
            tax_percentage=tax_in.tax_percentage,
            description=tax_in.description,
            is_active=tax_in.is_active,
        )
        db.add(tax)
        db.commit()
        db.refresh(tax)
        return tax

    @staticmethod
    def update_tax(db: Session, tax_id: uuid.UUID, tax_in: TaxUpdate) -> Optional[TaxConfiguration]:
        """Update an existing tax configuration."""
        tax = db.get(TaxConfiguration, tax_id)
        if not tax:
            return None

        update_data = tax_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tax, field, value)

        db.commit()
        db.refresh(tax)
        return tax

    @staticmethod
    def update_tax_status(db: Session, tax_id: uuid.UUID, is_active: bool) -> Optional[TaxConfiguration]:
        """Activate or deactivate a tax configuration."""
        tax = db.get(TaxConfiguration, tax_id)
        if not tax:
            return None

        tax.is_active = is_active
        db.commit()
        db.refresh(tax)
        return tax

    @staticmethod
    def delete_tax(db: Session, tax_id: uuid.UUID, hard_delete: bool = False) -> bool:
        """
        Safely deactivates or permanently deletes a tax configuration.
        Defaults to safe deactivation (`is_active=False`).
        """
        tax = db.get(TaxConfiguration, tax_id)
        if not tax:
            return False

        if hard_delete:
            db.delete(tax)
        else:
            tax.is_active = False

        db.commit()
        return True

    # --------------------------------------------------------
    # Monetary Tax Calculation Logic (Decimal Precision)
    # --------------------------------------------------------

    @staticmethod
    def calculate_tax(
        taxable_amount: Decimal,
        tax_percentage: Decimal,
        tax_name: Optional[str] = None,
        is_active: bool = True
    ) -> TaxCalculationResponse:
        """
        Pure function for tax calculation avoiding floating-point precision errors.
        
        Formula:
          tax_amount = taxable_amount * tax_percentage / 100
          final_amount = taxable_amount + tax_amount
        """
        if taxable_amount < Decimal("0.00"):
            raise ValueError(f"Taxable amount cannot be negative: {taxable_amount}")

        if tax_percentage < Decimal("0.00") or tax_percentage > Decimal("100.00"):
            raise ValueError(f"Invalid tax percentage: {tax_percentage}%. Must be between 0% and 100%.")

        # Quantize taxable amount to standard currency precision
        taxable_clean = taxable_amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # Precise calculation
        tax_amount_raw = taxable_clean * (tax_percentage / Decimal("100"))
        tax_amount = tax_amount_raw.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        final_amount = (taxable_clean + tax_amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        return TaxCalculationResponse(
            taxable_amount=taxable_clean,
            tax_percentage=tax_percentage,
            tax_amount=tax_amount,
            final_amount=final_amount,
            tax_name=tax_name,
            is_active=is_active
        )

    @staticmethod
    def calculate_tax_for_request(
        db: Session, req: TaxCalculationRequest
    ) -> TaxCalculationResponse:
        """
        Calculates tax using an existing DB tax configuration or an explicitly supplied rate.
        """
        if req.tax_id:
            tax = TaxService.get_tax_by_id(db, req.tax_id)
            if not tax:
                raise ValueError(f"Tax configuration with ID '{req.tax_id}' not found.")
            if not tax.is_active:
                raise ValueError(f"Tax configuration '{tax.name}' is currently inactive.")

            return TaxService.calculate_tax(
                taxable_amount=req.taxable_amount,
                tax_percentage=tax.tax_percentage,
                tax_name=tax.name,
                is_active=tax.is_active
            )
        else:
            assert req.tax_percentage is not None
            return TaxService.calculate_tax(
                taxable_amount=req.taxable_amount,
                tax_percentage=req.tax_percentage,
                tax_name=f"Custom Tax ({req.tax_percentage}%)",
                is_active=True
            )
