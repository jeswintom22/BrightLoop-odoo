"""P2 — subscription plan CRUD. Reads open to admin/staff/customer (customers
browse plans in the portal); writes admin/staff only."""

import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.deps import CurrentUser, require_roles
from app.models.subscription_plan import SubscriptionPlan
from app.schemas.subscription_plan import (
    SubscriptionPlanCreate,
    SubscriptionPlanListResponse,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
)

router = APIRouter(prefix="/subscription-plans", tags=["Subscription Plans"])

READ = Depends(require_roles("admin", "staff", "customer"))
WRITE = Depends(require_roles("admin", "staff"))


@router.get("", response_model=SubscriptionPlanListResponse)
def list_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    billing_frequency: Optional[str] = None,
    status: Optional[str] = None,
    available_only: bool = Query(
        False, description="Only plans inside their availability window"
    ),
    db: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    q = select(SubscriptionPlan)
    count_q = select(func.count()).select_from(SubscriptionPlan)

    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(SubscriptionPlan.name.ilike(like),
                        SubscriptionPlan.description.ilike(like)))
        count_q = count_q.where(or_(SubscriptionPlan.name.ilike(like),
                                    SubscriptionPlan.description.ilike(like)))
    if billing_frequency:
        q = q.where(SubscriptionPlan.billing_frequency == billing_frequency)
        count_q = count_q.where(SubscriptionPlan.billing_frequency == billing_frequency)
    if status:
        q = q.where(SubscriptionPlan.status == status)
        count_q = count_q.where(SubscriptionPlan.status == status)
    if available_only:
        from datetime import date as _date
        today = _date.today()
        q = q.where(
            SubscriptionPlan.status == "active",
            SubscriptionPlan.start_date <= today,
            or_(SubscriptionPlan.end_date.is_(None),
                SubscriptionPlan.end_date >= today),
        )
        count_q = count_q.where(
            SubscriptionPlan.status == "active",
            SubscriptionPlan.start_date <= today,
            or_(SubscriptionPlan.end_date.is_(None),
                SubscriptionPlan.end_date >= today),
        )

    total = db.scalar(count_q) or 0
    rows = db.scalars(
        q.order_by(SubscriptionPlan.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SubscriptionPlanListResponse(
        items=[SubscriptionPlanResponse.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{plan_id}", response_model=SubscriptionPlanResponse)
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    plan = db.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise AppError("NOT_FOUND", "Plan not found", 404)
    return plan


@router.post("", response_model=SubscriptionPlanResponse, status_code=201)
def create_plan(
    body: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    plan = SubscriptionPlan(**body.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.put("/{plan_id}", response_model=SubscriptionPlanResponse)
def update_plan(
    plan_id: int,
    body: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    plan = db.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise AppError("NOT_FOUND", "Plan not found", 404)
    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(plan, f, v)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=204)
def archive_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    plan = db.get(SubscriptionPlan, plan_id)
    if plan is None:
        raise AppError("NOT_FOUND", "Plan not found", 404)
    plan.status = "archived"  # safe delete — preserves subscription history
    db.commit()
