"""
Discount service — business logic for Discount CRUD, validation and atomic apply.

Key design decisions
--------------------
- validate_discount_code  → read-only; never touches usage_count.
- apply_discount          → locks the row where supported and conditionally increments
                            usage_count in the database to enforce limits concurrently.
- All monetary maths use Python Decimal (never float).
"""
import logging
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from app.models.discount import Discount
from app.models.product import Product
from app.schemas.discount import (
    DiscountCreate,
    DiscountUpdate,
    DiscountStatusUpdate,
    DiscountValidateResponse,
)

logger = logging.getLogger("brightloop.discount_service")


# ---------------------------------------------------------------------------
# Pure helpers (no DB dependency — easily unit-testable)
# ---------------------------------------------------------------------------

def calculate_discount_amount(
    discount_type: str,
    discount_value: Decimal,
    purchase_amount: Decimal,
) -> tuple[Decimal, Decimal]:
    """
    Returns (discount_amount, final_amount).

    - fixed:      discount_amount = min(discount_value, purchase_amount)
    - percentage: discount_amount = purchase_amount * discount_value / 100
    Both values are rounded to 2 d.p. (ROUND_HALF_UP).
    """
    two_dp = Decimal("0.01")
    if discount_type == "fixed":
        discount_amount = min(Decimal(str(discount_value)), Decimal(str(purchase_amount)))
    else:  # percentage
        discount_amount = (
            Decimal(str(purchase_amount)) * Decimal(str(discount_value)) / Decimal("100")
        ).quantize(two_dp, rounding=ROUND_HALF_UP)

    discount_amount = discount_amount.quantize(two_dp, rounding=ROUND_HALF_UP)
    final_amount = (Decimal(str(purchase_amount)) - discount_amount).quantize(
        two_dp, rounding=ROUND_HALF_UP
    )
    return discount_amount, final_amount


# ---------------------------------------------------------------------------
# Internal validation helper (shared by validate and apply)
# ---------------------------------------------------------------------------

def _run_discount_checks(
    discount: Discount,
    purchase_amount: Decimal,
    product_id: Optional[int],
) -> Optional[str]:
    """
    Returns an error message string if the discount is not applicable,
    or None if everything is fine.
    """
    now = datetime.now(timezone.utc)

    if not discount.is_active:
        return "This discount code is inactive."

    if discount.start_date.tzinfo is None:
        start = discount.start_date.replace(tzinfo=timezone.utc)
    else:
        start = discount.start_date

    if now < start:
        return "This discount code is not yet valid."

    if discount.expiry_date:
        expiry = (
            discount.expiry_date
            if discount.expiry_date.tzinfo
            else discount.expiry_date.replace(tzinfo=timezone.utc)
        )
        if now > expiry:
            return "This discount code has expired."

    if purchase_amount < Decimal(str(discount.minimum_purchase_amount)):
        return (
            f"Minimum purchase amount of {discount.minimum_purchase_amount} required."
        )

    if discount.usage_limit is not None and discount.usage_count >= discount.usage_limit:
        return "This discount code has reached its usage limit."

    # A product-restricted discount cannot be validated against an unspecified product.
    if discount.applicable_products and product_id is None:
        return "A product must be selected to validate this discount code."

    if product_id is not None and discount.applicable_products:
        applicable_ids = {p.id for p in discount.applicable_products}
        if product_id not in applicable_ids:
            return "This discount code is not valid for the selected product."

    return None  # All checks passed


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def _load_applicable_products(db: Session, product_ids: List[int]) -> List[Product]:
    """Load and validate a list of product IDs."""
    if not product_ids:
        return []
    products = db.execute(
        select(Product).where(Product.id.in_(product_ids))
    ).scalars().all()
    found_ids = {p.id for p in products}
    missing = set(product_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Products not found: {sorted(missing)}",
        )
    return list(products)


def create_discount(db: Session, discount_in: DiscountCreate) -> Discount:
    """Create a new Discount record and associate applicable products."""
    products = _load_applicable_products(db, discount_in.applicable_product_ids)

    db_discount = Discount(
        name=discount_in.name,
        code=discount_in.code,
        description=discount_in.description,
        discount_type=discount_in.discount_type,
        discount_value=discount_in.discount_value,
        start_date=discount_in.start_date,
        expiry_date=discount_in.expiry_date,
        minimum_purchase_amount=discount_in.minimum_purchase_amount,
        usage_limit=discount_in.usage_limit,
        is_active=discount_in.is_active,
        applicable_products=products,
    )

    try:
        db.add(db_discount)
        db.commit()
        db.refresh(db_discount)
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Discount code collision: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Discount code '{discount_in.code}' already exists.",
        ) from exc

    # Eagerly load relationships for the response
    db.refresh(db_discount)
    return db_discount


def get_discounts(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
) -> dict:
    """Return a paginated list of discounts, optionally filtered."""
    query = select(Discount).options(selectinload(Discount.applicable_products))

    if is_active is not None:
        query = query.where(Discount.is_active == is_active)

    if search:
        term = f"%{search.lower()}%"
        query = query.where(
            Discount.name.ilike(term) | Discount.code.ilike(term)
        )

    # Total count (separate query without pagination)
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total = db.execute(count_query).scalar_one()

    offset = (page - 1) * page_size
    discounts = db.execute(
        query.order_by(Discount.created_at.desc()).offset(offset).limit(page_size)
    ).scalars().all()

    pages = max(1, -(-total // page_size))  # ceiling division
    return {
        "items": discounts,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


def get_discount_by_id(db: Session, discount_id: uuid.UUID) -> Discount:
    """Fetch a single discount or raise 404."""
    discount = db.execute(
        select(Discount)
        .options(selectinload(Discount.applicable_products))
        .where(Discount.id == discount_id)
    ).scalar_one_or_none()

    if not discount:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discount {discount_id} not found.",
        )
    return discount


def update_discount(
    db: Session, discount_id: uuid.UUID, discount_in: DiscountUpdate
) -> Discount:
    """Partial update — only supplied (non-None) fields are changed."""
    discount = get_discount_by_id(db, discount_id)

    update_data = discount_in.model_dump(exclude_unset=True)
    product_ids = update_data.pop("applicable_product_ids", None)

    for field, value in update_data.items():
        setattr(discount, field, value)

    if product_ids is not None:
        discount.applicable_products = _load_applicable_products(db, product_ids)

    try:
        db.commit()
        db.refresh(discount)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Discount code already exists.",
        ) from exc

    return discount


def update_discount_status(
    db: Session, discount_id: uuid.UUID, status_in: DiscountStatusUpdate
) -> Discount:
    """Activate or deactivate a discount."""
    discount = get_discount_by_id(db, discount_id)
    discount.is_active = status_in.is_active
    db.commit()
    db.refresh(discount)
    return discount


def delete_discount(db: Session, discount_id: uuid.UUID, hard_delete: bool = False) -> dict:
    """
    Soft-delete (deactivate) by default.
    Pass hard_delete=True to remove the row entirely.
    """
    discount = get_discount_by_id(db, discount_id)

    if hard_delete:
        db.delete(discount)
        db.commit()
        return {"detail": "Discount permanently deleted."}

    discount.is_active = False
    db.commit()
    return {"detail": "Discount deactivated successfully."}


# ---------------------------------------------------------------------------
# Validate (dry-run — read-only)
# ---------------------------------------------------------------------------

def validate_discount_code(
    db: Session,
    code: str,
    purchase_amount: Decimal,
    product_id: Optional[int] = None,
) -> DiscountValidateResponse:
    """
    Check whether a discount code is applicable.
    Does NOT modify any database row.
    """
    discount = db.execute(
        select(Discount)
        .options(selectinload(Discount.applicable_products))
        .where(Discount.code == code)
    ).scalar_one_or_none()

    if not discount:
        return DiscountValidateResponse(
            is_valid=False,
            discount_amount=Decimal("0.00"),
            final_amount=purchase_amount,
            message="Invalid discount code.",
        )

    error_msg = _run_discount_checks(discount, purchase_amount, product_id)
    if error_msg:
        return DiscountValidateResponse(
            is_valid=False,
            discount_amount=Decimal("0.00"),
            final_amount=purchase_amount,
            message=error_msg,
        )

    discount_amount, final_amount = calculate_discount_amount(
        discount.discount_type, discount.discount_value, purchase_amount
    )

    return DiscountValidateResponse(
        is_valid=True,
        discount_amount=discount_amount,
        final_amount=final_amount,
        message="Discount code is valid.",
        discount=discount,
    )


# ---------------------------------------------------------------------------
# Apply (transactional — increments usage_count atomically)
# ---------------------------------------------------------------------------

def apply_discount(
    db: Session,
    code: str,
    purchase_amount: Decimal,
    product_id: Optional[int] = None,
) -> DiscountValidateResponse:
    """
    Validate the discount code AND atomically increment usage_count.
    Uses SELECT … FOR UPDATE to prevent race conditions.
    """
    # Row-lock the discount row so concurrent requests queue up here.
    # SQLite does not support SELECT … FOR UPDATE; skip the lock for SQLite (single-writer anyway).
    _is_sqlite = db.get_bind().dialect.name == "sqlite"
    base_query = (
        select(Discount)
        .options(selectinload(Discount.applicable_products))
        .where(Discount.code == code)
    )
    if not _is_sqlite:
        base_query = base_query.with_for_update()
    discount = db.execute(base_query).scalar_one_or_none()

    if not discount:
        return DiscountValidateResponse(
            is_valid=False,
            discount_amount=Decimal("0.00"),
            final_amount=purchase_amount,
            message="Invalid discount code.",
        )

    error_msg = _run_discount_checks(discount, purchase_amount, product_id)
    if error_msg:
        return DiscountValidateResponse(
            is_valid=False,
            discount_amount=Decimal("0.00"),
            final_amount=purchase_amount,
            message=error_msg,
        )

    discount_amount, final_amount = calculate_discount_amount(
        discount.discount_type, discount.discount_value, purchase_amount
    )

    # Keep the usage limit safe even on databases without row-level SELECT locks.
    result = db.execute(
        update(Discount)
        .where(
            Discount.id == discount.id,
            Discount.is_active.is_(True),
            or_(
                Discount.usage_limit.is_(None),
                Discount.usage_count < Discount.usage_limit,
            ),
        )
        .values(usage_count=Discount.usage_count + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        current_discount = db.execute(
            select(Discount)
            .options(selectinload(Discount.applicable_products))
            .where(Discount.id == discount.id)
        ).scalar_one_or_none()
        if current_discount is None:
            message = "Invalid discount code."
        else:
            message = (
                _run_discount_checks(current_discount, purchase_amount, product_id)
                or "This discount code has reached its usage limit."
            )
        return DiscountValidateResponse(
            is_valid=False,
            discount_amount=Decimal("0.00"),
            final_amount=purchase_amount,
            message=message,
        )

    db.commit()
    db.refresh(discount)

    return DiscountValidateResponse(
        is_valid=True,
        discount_amount=discount_amount,
        final_amount=final_amount,
        message="Discount applied successfully.",
        discount=discount,
    )
