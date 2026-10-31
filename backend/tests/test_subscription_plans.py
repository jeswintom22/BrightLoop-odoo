import pytest
from datetime import date, timedelta
from decimal import Decimal
from pydantic import ValidationError
from app.db.session import SessionLocal
from app.services.product_service import ProductService
from app.services.subscription_plan_service import SubscriptionPlanService
from app.schemas.product import ProductCreate
from app.schemas.product_variant import ProductVariantCreate
from app.schemas.subscription_plan import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_product_and_variant(db_session):
    prod = ProductService.create_product(
        db_session,
        ProductCreate(
            name="SaaS Suite",
            product_type="service",
            sales_price=Decimal("100.00"),
            cost_price=Decimal("20.00"),
        ),
    )
    var = ProductService.create_variant(
        db_session,
        prod.id,
        ProductVariantCreate(
            name="Pro Config",
            sales_price=Decimal("150.00"),
            cost_price=Decimal("30.00"),
        ),
    )
    return prod, var


def test_plan_schema_validations():
    """Verify Pydantic validations for dates, frequencies, and minimum quantities."""
    today = date.today()

    # Invalid billing frequency
    with pytest.raises(ValidationError):
        SubscriptionPlanCreate(
            name="Plan X",
            product_id=1,
            price=Decimal("50.00"),
            billing_frequency="hourly",  # invalid
            minimum_quantity=1,
            available_from=today,
        )

    # Invalid date range (end before start)
    with pytest.raises(ValidationError):
        SubscriptionPlanCreate(
            name="Plan Y",
            product_id=1,
            price=Decimal("50.00"),
            billing_frequency="monthly",
            minimum_quantity=1,
            available_from=today,
            available_until=today - timedelta(days=5),
        )

    # Minimum quantity < 1
    with pytest.raises(ValidationError):
        SubscriptionPlanCreate(
            name="Plan Z",
            product_id=1,
            price=Decimal("50.00"),
            billing_frequency="monthly",
            minimum_quantity=0,
            available_from=today,
        )


def test_subscription_plan_crud_and_lifecycle(db_session, sample_product_and_variant):
    prod, var = sample_product_and_variant
    today = date.today()

    # 1. Create Subscription Plan
    plan_in = SubscriptionPlanCreate(
        name="Pro Annual Plan",
        description="Comprehensive 1-year SaaS subscription",
        product_id=prod.id,
        product_variant_id=var.id,
        price=Decimal("1200.00"),
        billing_frequency="yearly",
        minimum_quantity=2,
        available_from=today,
        available_until=today + timedelta(days=365),
        status="active",
        allow_pause=True,
        allow_renewal=True,
        allow_early_closure=False,
        automatic_closure=True,
    )
    plan = SubscriptionPlanService.create_plan(db_session, plan_in)
    assert plan.id is not None
    assert plan.name == "Pro Annual Plan"
    assert plan.billing_frequency == "yearly"
    plan_id = plan.id

    # 2. Get Plan by ID
    fetched = SubscriptionPlanService.get_plan_by_id(db_session, plan_id)
    assert fetched is not None
    assert fetched.product.name == "SaaS Suite"
    assert fetched.variant.name == "Pro Config"

    # 3. Business Logic Helpers
    # Availability check
    is_avail, _ = SubscriptionPlanService.validate_plan_availability(fetched, today)
    assert is_avail is True

    # Minimum quantity check
    is_valid_qty, _ = SubscriptionPlanService.validate_minimum_quantity(fetched, 1)
    assert is_valid_qty is False
    is_valid_qty, _ = SubscriptionPlanService.validate_minimum_quantity(fetched, 2)
    assert is_valid_qty is True

    # Permissions
    assert SubscriptionPlanService.check_pause_permission(fetched) is True
    assert SubscriptionPlanService.check_renewal_permission(fetched) is True
    assert SubscriptionPlanService.check_early_closure_permission(fetched) is False
    assert SubscriptionPlanService.is_auto_closure_enabled(fetched) is True

    # 4. List and Filter Plans
    items, total, pages = SubscriptionPlanService.get_plans(
        db_session, status="active", billing_frequency="yearly", product_id=prod.id
    )
    assert total >= 1
    assert any(p.id == plan_id for p in items)

    # 5. Update Plan
    updated = SubscriptionPlanService.update_plan(
        db_session, plan_id, SubscriptionPlanUpdate(price=Decimal("1100.00"), allow_early_closure=True)
    )
    assert updated.price == Decimal("1100.00")
    assert updated.allow_early_closure is True

    # 6. Status Update
    deactivated = SubscriptionPlanService.update_plan_status(db_session, plan_id, "inactive")
    assert deactivated.status == "inactive"
    is_avail, msg = SubscriptionPlanService.validate_plan_availability(deactivated, today)
    assert is_avail is False

    # 7. Safe Delete (Archive)
    SubscriptionPlanService.delete_plan(db_session, plan_id, hard_delete=False)
    archived = SubscriptionPlanService.get_plan_by_id(db_session, plan_id)
    assert archived.status == "archived"

    # 8. Hard Delete
    SubscriptionPlanService.delete_plan(db_session, plan_id, hard_delete=True)
    assert SubscriptionPlanService.get_plan_by_id(db_session, plan_id) is None
