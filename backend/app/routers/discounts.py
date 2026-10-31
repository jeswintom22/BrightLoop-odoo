"""
Discount router — REST endpoints for Discount management.

Mounted in main.py under both /api and /api/v1 prefixes.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import require_roles
from app.schemas.discount import (
    DiscountCreate,
    DiscountUpdate,
    DiscountStatusUpdate,
    DiscountResponse,
    DiscountListResponse,
    DiscountValidateRequest,
    DiscountApplyRequest,
    DiscountValidateResponse,
)
from app.services import discount_service

router = APIRouter(prefix="/discounts", tags=["Discounts"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=DiscountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new discount",
    dependencies=[Depends(require_roles("admin", "staff"))],
)
def create_discount(discount_in: DiscountCreate, db: Session = Depends(get_db)):
    """
    Create a discount code with optional product-level restrictions.

    - **code** is normalised to UPPER CASE automatically.
    - **applicable_product_ids**: leave empty to allow the discount on any product.
    - **usage_limit**: leave null for unlimited uses.
    """
    return discount_service.create_discount(db, discount_in)


@router.get(
    "",
    response_model=DiscountListResponse,
    summary="List discounts (paginated)",
)
def list_discounts(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name or code"),
    db: Session = Depends(get_db),
):
    """List all discounts with pagination, optional status filter and text search."""
    return discount_service.get_discounts(
        db, page=page, page_size=page_size, is_active=is_active, search=search
    )


@router.get(
    "/{discount_id}",
    response_model=DiscountResponse,
    summary="Get a discount by ID",
)
def get_discount(discount_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve a single discount including its applicable products."""
    return discount_service.get_discount_by_id(db, discount_id)


@router.put(
    "/{discount_id}",
    response_model=DiscountResponse,
    summary="Update a discount",
    dependencies=[Depends(require_roles("admin", "staff"))],
)
def update_discount(
    discount_id: uuid.UUID,
    discount_in: DiscountUpdate,
    db: Session = Depends(get_db),
):
    """
    Partial update — only supplied fields are changed.
    To replace the product list, provide **applicable_product_ids**.
    """
    return discount_service.update_discount(db, discount_id, discount_in)


@router.delete(
    "/{discount_id}",
    summary="Deactivate (soft-delete) a discount",
    dependencies=[Depends(require_roles("admin", "staff"))],
)
def delete_discount(
    discount_id: uuid.UUID,
    hard_delete: bool = Query(False, description="Set true to permanently delete"),
    db: Session = Depends(get_db),
):
    """
    By default performs a soft-delete (sets `is_active=False`).
    Pass `?hard_delete=true` to permanently remove the row.
    """
    return discount_service.delete_discount(db, discount_id, hard_delete=hard_delete)


@router.patch(
    "/{discount_id}/status",
    response_model=DiscountResponse,
    summary="Activate or deactivate a discount",
    dependencies=[Depends(require_roles("admin", "staff"))],
)
def update_discount_status(
    discount_id: uuid.UUID,
    status_in: DiscountStatusUpdate,
    db: Session = Depends(get_db),
):
    """Toggle `is_active` for a discount without touching any other field."""
    return discount_service.update_discount_status(db, discount_id, status_in)


# ---------------------------------------------------------------------------
# Validate / Apply
# ---------------------------------------------------------------------------

@router.post(
    "/validate",
    response_model=DiscountValidateResponse,
    summary="Validate a discount code (dry-run — no usage increment)",
    dependencies=[Depends(require_roles("admin", "staff"))],
)
def validate_discount(
    request: DiscountValidateRequest,
    db: Session = Depends(get_db),
):
    """
    Check whether a discount code is valid for the given purchase amount.
    **Does not** increment `usage_count` — safe to call from cart preview / checkout preview.
    """
    return discount_service.validate_discount_code(
        db,
        code=request.code,
        purchase_amount=request.purchase_amount,
        product_id=request.product_id,
    )


@router.post(
    "/apply",
    response_model=DiscountValidateResponse,
    summary="Apply a discount code (increments usage_count atomically)",
    dependencies=[Depends(require_roles("admin", "staff"))],
)
def apply_discount(
    request: DiscountApplyRequest,
    db: Session = Depends(get_db),
):
    """
    Validate **and** consume a discount code in a single atomic transaction.
    Uses `SELECT … FOR UPDATE` to prevent concurrent over-use.
    Call this endpoint only at the moment of confirmed purchase — not for preview.
    """
    return discount_service.apply_discount(
        db,
        code=request.code,
        purchase_amount=request.purchase_amount,
        product_id=request.product_id,
    )
