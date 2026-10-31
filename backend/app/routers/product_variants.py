from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.product_service import ProductService
from app.schemas.product_variant import (
    ProductVariantUpdate,
    ProductVariantResponse,
)

router = APIRouter(prefix="/variants", tags=["Product Variants"])


@router.get("/{variant_id}", response_model=ProductVariantResponse, summary="Get variant details")
def get_variant(variant_id: int, db: Session = Depends(get_db)):
    variant = ProductService.get_variant_by_id(db, variant_id)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found."
        )
    return variant


@router.put("/{variant_id}", response_model=ProductVariantResponse, summary="Update an existing variant")
def update_variant(
    variant_id: int,
    variant_in: ProductVariantUpdate,
    db: Session = Depends(get_db)
):
    variant = ProductService.update_variant(db, variant_id, variant_in)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found."
        )
    return variant


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a variant")
def delete_variant(variant_id: int, db: Session = Depends(get_db)):
    success = ProductService.delete_variant(db, variant_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found."
        )
    return None
