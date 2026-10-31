"""P2 — taxes & discounts CRUD (admin/staff writes; all roles read)."""

import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.db.session import get_db
from app.deps import CurrentUser, require_roles
from app.models.discount import Discount
from app.models.product import Product
from app.models.tax import TaxConfiguration
from app.schemas.catalog_admin import (
    DiscountCreate,
    DiscountListResponse,
    DiscountResponse,
    DiscountUpdate,
    TaxCreate,
    TaxListResponse,
    TaxResponse,
    TaxUpdate,
)

router = APIRouter(tags=["Catalog Admin"])

READ = Depends(require_roles("admin", "staff", "customer"))
WRITE = Depends(require_roles("admin", "staff"))


# --- taxes ---------------------------------------------------------------------


@router.get("/taxes", response_model=TaxListResponse)
def list_taxes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    total = db.scalar(select(func.count()).select_from(TaxConfiguration)) or 0
    rows = db.scalars(
        select(TaxConfiguration)
        .order_by(TaxConfiguration.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TaxListResponse(
        items=[TaxResponse.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/taxes", response_model=TaxResponse, status_code=201)
def create_tax(
    body: TaxCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    tax = TaxConfiguration(**body.model_dump())
    db.add(tax)
    db.commit()
    db.refresh(tax)
    return tax


@router.put("/taxes/{tax_id}", response_model=TaxResponse)
def update_tax(
    tax_id: int,
    body: TaxUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    tax = db.get(TaxConfiguration, tax_id)
    if tax is None:
        raise AppError("NOT_FOUND", "Tax not found", 404)
    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(tax, f, v)
    db.commit()
    db.refresh(tax)
    return tax


@router.delete("/taxes/{tax_id}", status_code=204)
def deactivate_tax(
    tax_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    tax = db.get(TaxConfiguration, tax_id)
    if tax is None:
        raise AppError("NOT_FOUND", "Tax not found", 404)
    tax.is_active = False
    db.commit()


# --- discounts -------------------------------------------------------------------


def _discount_out(d: Discount) -> DiscountResponse:
    data = DiscountResponse.model_validate(d)
    data.product_ids = [p.id for p in d.applicable_products]
    return data


@router.get("/discounts", response_model=DiscountListResponse)
def list_discounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    q = select(Discount).options(selectinload(Discount.applicable_products))
    count_q = select(func.count()).select_from(Discount)
    if is_active is not None:
        q = q.where(Discount.is_active == is_active)
        count_q = count_q.where(Discount.is_active == is_active)
    total = db.scalar(count_q) or 0
    rows = db.scalars(
        q.order_by(Discount.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return DiscountListResponse(
        items=[_discount_out(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/discounts", response_model=DiscountResponse, status_code=201)
def create_discount(
    body: DiscountCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    if db.scalar(select(Discount).where(Discount.code == body.code)):
        raise AppError("CONFLICT", f"Discount code '{body.code}' already exists", 409)
    product_ids = body.model_dump().pop("product_ids")
    discount = Discount(**body.model_dump(exclude={"product_ids"}))
    if product_ids:
        products = db.scalars(
            select(Product).where(Product.id.in_(product_ids))
        ).all()
        if len(products) != len(set(product_ids)):
            raise AppError("VALIDATION", "Unknown product id in product_ids", 400)
        discount.applicable_products = list(products)
    db.add(discount)
    db.commit()
    db.refresh(discount)
    return _discount_out(discount)


@router.put("/discounts/{discount_id}", response_model=DiscountResponse)
def update_discount(
    discount_id: int,
    body: DiscountUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    discount = db.get(Discount, discount_id)
    if discount is None:
        raise AppError("NOT_FOUND", "Discount not found", 404)
    data = body.model_dump(exclude_unset=True)
    product_ids = data.pop("product_ids", None)
    for f, v in data.items():
        setattr(discount, f, v)
    if product_ids is not None:
        products = db.scalars(
            select(Product).where(Product.id.in_(product_ids))
        ).all()
        if len(products) != len(set(product_ids)):
            raise AppError("VALIDATION", "Unknown product id in product_ids", 400)
        discount.applicable_products = list(products)
    db.commit()
    db.refresh(discount)
    return _discount_out(discount)


@router.delete("/discounts/{discount_id}", status_code=204)
def deactivate_discount(
    discount_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    discount = db.get(Discount, discount_id)
    if discount is None:
        raise AppError("NOT_FOUND", "Discount not found", 404)
    discount.is_active = False
    db.commit()
