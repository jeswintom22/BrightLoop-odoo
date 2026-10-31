import math
import uuid
from datetime import date
from typing import Optional, Tuple, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from app.models.subscription_plan import SubscriptionPlan
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.schemas.subscription_plan import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
)


class SubscriptionPlanService:
    @staticmethod
    def get_plans(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        billing_frequency: Optional[str] = None,
        product_id: Optional[int] = None,
    ) -> Tuple[List[SubscriptionPlan], int, int]:
        """
        Retrieves paginated subscription plans with filters.
        Returns: (items, total_count, total_pages)
        """
        query = select(SubscriptionPlan).options(
            selectinload(SubscriptionPlan.product),
            selectinload(SubscriptionPlan.variant),
        )

        if status:
            query = query.where(SubscriptionPlan.status == status.lower())
        if billing_frequency:
            query = query.where(SubscriptionPlan.billing_frequency == billing_frequency.lower())
        if product_id:
            query = query.where(SubscriptionPlan.product_id == product_id)

        # Count total matching records
        count_stmt = select(func.count()).select_from(query.order_by(None).subquery())
        total = db.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        pages = math.ceil(total / page_size) if total > 0 else 0

        items = db.scalars(
            query.order_by(SubscriptionPlan.created_at.desc()).offset(offset).limit(page_size)
        ).all()
        return list(items), total, pages

    @staticmethod
    def get_plan_by_id(db: Session, plan_id: uuid.UUID) -> Optional[SubscriptionPlan]:
        """Fetch a specific subscription plan by UUID with product/variant details."""
        stmt = (
            select(SubscriptionPlan)
            .options(
                selectinload(SubscriptionPlan.product),
                selectinload(SubscriptionPlan.variant),
            )
            .where(SubscriptionPlan.id == plan_id)
        )
        return db.scalar(stmt)

    @staticmethod
    def create_plan(db: Session, plan_in: SubscriptionPlanCreate) -> SubscriptionPlan:
        """
        Create a new subscription plan after validating parent product and variant.
        """
        # Validate parent product exists
        product = db.get(Product, plan_in.product_id)
        if not product:
            raise ValueError(f"Parent product with ID {plan_in.product_id} does not exist.")

        # Validate variant belongs to the parent product if specified
        if plan_in.product_variant_id:
            variant = db.get(ProductVariant, plan_in.product_variant_id)
            if not variant:
                raise ValueError(f"Product variant with ID {plan_in.product_variant_id} does not exist.")
            if variant.product_id != plan_in.product_id:
                raise ValueError(
                    f"Product variant {plan_in.product_variant_id} does not belong to product {plan_in.product_id}."
                )

        plan = SubscriptionPlan(
            name=plan_in.name,
            description=plan_in.description,
            product_id=plan_in.product_id,
            product_variant_id=plan_in.product_variant_id,
            price=plan_in.price,
            billing_frequency=plan_in.billing_frequency,
            minimum_quantity=plan_in.minimum_quantity,
            available_from=plan_in.available_from,
            available_until=plan_in.available_until,
            status=plan_in.status,
            allow_pause=plan_in.allow_pause,
            allow_renewal=plan_in.allow_renewal,
            allow_early_closure=plan_in.allow_early_closure,
            automatic_closure=plan_in.automatic_closure,
        )

        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def update_plan(
        db: Session, plan_id: uuid.UUID, plan_in: SubscriptionPlanUpdate
    ) -> Optional[SubscriptionPlan]:
        """Update an existing subscription plan with relational integrity checks."""
        plan = SubscriptionPlanService.get_plan_by_id(db, plan_id)
        if not plan:
            return None

        update_data = plan_in.model_dump(exclude_unset=True)

        # Validate product_id if changing
        target_product_id = update_data.get("product_id", plan.product_id)
        if "product_id" in update_data:
            product = db.get(Product, target_product_id)
            if not product:
                raise ValueError(f"Product with ID {target_product_id} does not exist.")

        # Validate product_variant_id if changing
        if "product_variant_id" in update_data and update_data["product_variant_id"] is not None:
            variant = db.get(ProductVariant, update_data["product_variant_id"])
            if not variant:
                raise ValueError(f"Product variant with ID {update_data['product_variant_id']} does not exist.")
            if variant.product_id != target_product_id:
                raise ValueError(
                    f"Product variant {variant.id} does not belong to product {target_product_id}."
                )

        # Validate dates consistency if updating either
        new_from = update_data.get("available_from", plan.available_from)
        new_until = update_data.get("available_until", plan.available_until)
        if new_until and new_from and new_until < new_from:
            raise ValueError("available_until date cannot be before available_from date.")

        for field, value in update_data.items():
            setattr(plan, field, value)

        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def update_plan_status(
        db: Session, plan_id: uuid.UUID, new_status: str
    ) -> Optional[SubscriptionPlan]:
        """Activate, deactivate, or archive a subscription plan."""
        plan = db.get(SubscriptionPlan, plan_id)
        if not plan:
            return None

        plan.status = new_status.lower()
        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def delete_plan(db: Session, plan_id: uuid.UUID, hard_delete: bool = False) -> bool:
        """
        Safely deletes or archives a plan.
        If hard_delete=False (safe default), transitions status to 'archived'.
        """
        plan = db.get(SubscriptionPlan, plan_id)
        if not plan:
            return False

        if hard_delete:
            db.delete(plan)
        else:
            plan.status = "archived"

        db.commit()
        return True

    # --------------------------------------------------------
    # Business Logic & Lifecycle Permissions
    # --------------------------------------------------------

    @staticmethod
    def validate_plan_availability(
        plan: SubscriptionPlan, target_date: Optional[date] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a plan is currently available for subscription.
        Checks active status and date boundaries.
        """
        if plan.status != "active":
            return False, f"Plan '{plan.name}' is currently {plan.status}."

        check_date = target_date or date.today()
        if check_date < plan.available_from:
            return False, f"Plan '{plan.name}' is not yet available (starts on {plan.available_from})."

        if plan.available_until and check_date > plan.available_until:
            return False, f"Plan '{plan.name}' has expired (ended on {plan.available_until})."

        return True, None

    @staticmethod
    def validate_minimum_quantity(plan: SubscriptionPlan, quantity: int) -> Tuple[bool, Optional[str]]:
        """Validates requested quantity against plan's minimum threshold."""
        if quantity < plan.minimum_quantity:
            return False, f"Quantity {quantity} is below minimum required quantity of {plan.minimum_quantity}."
        return True, None

    @staticmethod
    def check_pause_permission(plan: SubscriptionPlan) -> bool:
        """Returns whether subscribers are permitted to pause subscriptions on this plan."""
        return plan.allow_pause

    @staticmethod
    def check_renewal_permission(plan: SubscriptionPlan) -> bool:
        """Returns whether subscriptions on this plan can be renewed."""
        return plan.allow_renewal

    @staticmethod
    def check_early_closure_permission(plan: SubscriptionPlan) -> bool:
        """Returns whether subscriptions on this plan allow early closure."""
        return plan.allow_early_closure

    @staticmethod
    def is_auto_closure_enabled(plan: SubscriptionPlan) -> bool:
        """Returns whether plan auto-closes when availability window ends."""
        return plan.automatic_closure
