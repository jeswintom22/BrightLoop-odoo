from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.product_service import ProductService
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)
from app.schemas.product_variant import (
    ProductVariantCreate,
    ProductVariantResponse,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductListResponse, summary="List products with search and pagination")
def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for name or notes"),
    product_type: Optional[str] = Query(None, description="Filter by type (goods, service, digital, subscription)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
):
    items, total, pages = ProductService.get_products(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        product_type=product_type,
        is_active=is_active,
    )
    return ProductListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Create a new product")
def create_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    return ProductService.create_product(db, product_in)


@router.get("/{product_id}", response_model=ProductResponse, summary="Get product details")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found."
        )
    return product


@router.put("/{product_id}", response_model=ProductResponse, summary="Update an existing product")
def update_product(product_id: int, product_in: ProductUpdate, db: Session = Depends(get_db)):
    product = ProductService.update_product(db, product_id, product_in)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found."
        )
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a product")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    success = ProductService.delete_product(db, product_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found."
        )
    return None


# --------------------------------------------------------
# Nested Variant Endpoints for clean ergonomics
# --------------------------------------------------------

@router.get("/{product_id}/variants", response_model=List[ProductVariantResponse], summary="List variants for a product")
def list_product_variants(product_id: int, db: Session = Depends(get_db)):
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent product with ID {product_id} not found."
        )
    return ProductService.get_variants_by_product_id(db, product_id)


@router.post(
    "/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a variant to a product",
)
def add_product_variant(
    product_id: int,
    variant_in: ProductVariantCreate,
    db: Session = Depends(get_db)
):
    variant = ProductService.create_variant(db, product_id, variant_in)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent product with ID {product_id} not found."
        )
    return variant
