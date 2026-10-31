import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.deps import require_roles
from app.services.subscription_plan_service import SubscriptionPlanService
from app.schemas.subscription_plan import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanStatusUpdate,
    SubscriptionPlanResponse,
    SubscriptionPlanListResponse,
)

router = APIRouter(prefix="/plans", tags=["Subscription Plans"])


def _format_plan_response(plan) -> SubscriptionPlanResponse:
    """Helper to attach human-readable product and variant names."""
    res = SubscriptionPlanResponse.model_validate(plan)
    if plan.product:
        res.product_name = plan.product.name
    if plan.variant:
        res.variant_name = plan.variant.name
    return res


@router.post(
    "",
    response_model=SubscriptionPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a subscription plan",
    dependencies=[Depends(require_roles("admin", "staff"))],
)
def create_plan(plan_in: SubscriptionPlanCreate, db: Session = Depends(get_db)):
    try:
        plan = SubscriptionPlanService.create_plan(db, plan_in)
        return _format_plan_response(plan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "",
    response_model=SubscriptionPlanListResponse,
    summary="List subscription plans with filters and pagination",
)
def list_plans(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (active, inactive, archived)"),
    billing_frequency: Optional[str] = Query(None, description="Filter by frequency (daily, weekly, monthly, yearly)"),
    product_id: Optional[int] = Query(None, description="Filter by associated product ID"),
    db: Session = Depends(get_db),
):
    items, total, pages = SubscriptionPlanService.get_plans(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        billing_frequency=billing_frequency,
        product_id=product_id,
    )
    return SubscriptionPlanListResponse(
        items=[_format_plan_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{plan_id}", response_model=SubscriptionPlanResponse, summary="Retrieve a specific plan")
def get_plan(plan_id: uuid.UUID, db: Session = Depends(get_db)):
    plan = SubscriptionPlanService.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription plan '{plan_id}' not found."
        )
    return _format_plan_response(plan)


@router.put("/{plan_id}", response_model=SubscriptionPlanResponse, summary="Update an existing plan", dependencies=[Depends(require_roles("admin", "staff"))])
def update_plan(
    plan_id: uuid.UUID,
    plan_in: SubscriptionPlanUpdate,
    db: Session = Depends(get_db)
):
    try:
        plan = SubscriptionPlanService.update_plan(db, plan_id, plan_in)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription plan '{plan_id}' not found."
            )
        return _format_plan_response(plan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{plan_id}", summary="Safely archive or delete a plan", dependencies=[Depends(require_roles("admin", "staff"))])
def delete_plan(
    plan_id: uuid.UUID,
    hard_delete: bool = Query(False, description="Permanently delete from database (false archives)"),
    db: Session = Depends(get_db)
):
    success = SubscriptionPlanService.delete_plan(db, plan_id, hard_delete=hard_delete)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription plan '{plan_id}' not found."
        )
    return {
        "success": True,
        "message": f"Plan '{plan_id}' {'permanently deleted' if hard_delete else 'archived'} successfully."
    }


@router.patch("/{plan_id}/status", response_model=SubscriptionPlanResponse, summary="Update plan status", dependencies=[Depends(require_roles("admin", "staff"))])
def update_plan_status(
    plan_id: uuid.UUID,
    status_in: SubscriptionPlanStatusUpdate,
    db: Session = Depends(get_db)
):
    plan = SubscriptionPlanService.update_plan_status(db, plan_id, status_in.status)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription plan '{plan_id}' not found."
        )
    return _format_plan_response(plan)
