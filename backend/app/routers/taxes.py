import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.tax_service import TaxService
from app.schemas.tax import (
    TaxCreate,
    TaxUpdate,
    TaxStatusUpdate,
    TaxResponse,
    TaxCalculationRequest,
    TaxCalculationResponse,
)

router = APIRouter(prefix="/taxes", tags=["Tax Configurations"])


@router.post(
    "",
    response_model=TaxResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tax configuration",
)
def create_tax(tax_in: TaxCreate, db: Session = Depends(get_db)):
    try:
        return TaxService.create_tax(db, tax_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=List[TaxResponse],
    summary="List all tax configurations",
)
def list_taxes(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
):
    return TaxService.get_taxes(db, is_active=is_active)


@router.get("/{tax_id}", response_model=TaxResponse, summary="Retrieve a tax configuration")
def get_tax(tax_id: uuid.UUID, db: Session = Depends(get_db)):
    tax = TaxService.get_tax_by_id(db, tax_id)
    if not tax:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax configuration '{tax_id}' not found."
        )
    return tax


@router.put("/{tax_id}", response_model=TaxResponse, summary="Update a tax configuration")
def update_tax(
    tax_id: uuid.UUID,
    tax_in: TaxUpdate,
    db: Session = Depends(get_db)
):
    try:
        tax = TaxService.update_tax(db, tax_id, tax_in)
        if not tax:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tax configuration '{tax_id}' not found."
            )
        return tax
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{tax_id}", summary="Safely deactivate or delete a tax configuration")
def delete_tax(
    tax_id: uuid.UUID,
    hard_delete: bool = Query(False, description="Permanently delete from database (false deactivates)"),
    db: Session = Depends(get_db)
):
    success = TaxService.delete_tax(db, tax_id, hard_delete=hard_delete)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax configuration '{tax_id}' not found."
        )
    return {
        "success": True,
        "message": f"Tax configuration '{tax_id}' {'permanently deleted' if hard_delete else 'deactivated'} successfully."
    }


@router.patch("/{tax_id}/status", response_model=TaxResponse, summary="Update tax active status")
def update_tax_status(
    tax_id: uuid.UUID,
    status_in: TaxStatusUpdate,
    db: Session = Depends(get_db)
):
    tax = TaxService.update_tax_status(db, tax_id, status_in.is_active)
    if not tax:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax configuration '{tax_id}' not found."
        )
    return tax


@router.post(
    "/calculate",
    response_model=TaxCalculationResponse,
    summary="Calculate tax amount and gross total with Decimal precision",
)
def calculate_tax(request: TaxCalculationRequest, db: Session = Depends(get_db)):
    try:
        return TaxService.calculate_tax_for_request(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
