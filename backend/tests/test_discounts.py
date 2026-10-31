"""
Tests for Discount management module.

Test coverage:
- Pydantic schema validation (invalid type, percentage > 100, negative value, bad dates)
- Pure Decimal calculation helpers
- Service-layer CRUD (create, retrieve, update, status toggle, delete)
- validate_discount_code — checks all rejection scenarios, does NOT increment usage_count
- apply_discount — increments usage_count, enforces usage_limit

Note: API route coverage is validated via live server integration tests.
This file follows the project convention of testing through the service layer,
consistent with test_products.py and test_subscription_plans.py.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db.session import SessionLocal
from app.schemas.discount import DiscountCreate, DiscountStatusUpdate
from app.models.product import Product
from app.services.discount_service import (
    calculate_discount_amount,
    create_discount,
    get_discount_by_id,
    validate_discount_code,
    apply_discount,
    update_discount,
    update_discount_status,
    delete_discount,
)
from app.schemas.discount import DiscountUpdate


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _future(days: int = 30) -> datetime:
    return _now() + timedelta(days=days)


def _past(days: int = 1) -> datetime:
    return _now() - timedelta(days=days)


def _schema(code: str, **overrides) -> DiscountCreate:
    defaults = dict(
        name="Test Discount",
        code=code,
        discount_type="percentage",
        discount_value=Decimal("10"),
        start_date=_now(),
        expiry_date=_future(30),
        minimum_purchase_amount=Decimal("0.00"),
        is_active=True,
        applicable_product_ids=[],
    )
    defaults.update(overrides)
    return DiscountCreate(**defaults)


# ===========================================================================
# 1. Schema validation (no DB needed)
# ===========================================================================

def test_invalid_discount_type_rejected():
    with pytest.raises(ValidationError) as exc_info:
        DiscountCreate(
            name="Bad",
            code="BAD10",
            discount_type="points",
            discount_value=Decimal("10"),
            start_date=_now(),
            applicable_product_ids=[],
        )
    assert "discount_type must be one of" in str(exc_info.value)


def test_percentage_over_100_rejected():
    with pytest.raises(ValidationError) as exc_info:
        DiscountCreate(
            name="Over",
            code="OVER",
            discount_type="percentage",
            discount_value=Decimal("150"),
            start_date=_now(),
            applicable_product_ids=[],
        )
    assert "cannot exceed 100%" in str(exc_info.value)


def test_negative_discount_value_rejected():
    with pytest.raises(ValidationError):
        DiscountCreate(
            name="Neg",
            code="NEG",
            discount_type="fixed",
            discount_value=Decimal("-5"),
            start_date=_now(),
            applicable_product_ids=[],
        )


def test_expiry_before_start_rejected():
    with pytest.raises(ValidationError) as exc_info:
        DiscountCreate(
            name="BadDate",
            code="BADDATE",
            discount_type="fixed",
            discount_value=Decimal("10"),
            start_date=_future(5),
            expiry_date=_future(2),
            applicable_product_ids=[],
        )
    assert "expiry_date must be after start_date" in str(exc_info.value)


def test_code_uppercased_automatically():
    obj = DiscountCreate(
        name="Lower",
        code="lower20",
        discount_type="fixed",
        discount_value=Decimal("20"),
        start_date=_now(),
        applicable_product_ids=[],
    )
    assert obj.code == "LOWER20"


# ===========================================================================
# 2. Pure calculation tests (no DB needed)
# ===========================================================================

def test_fixed_discount():
    d, f = calculate_discount_amount("fixed", Decimal("100"), Decimal("1000"))
    assert d == Decimal("100.00") and f == Decimal("900.00")


def test_fixed_discount_capped_at_purchase_amount():
    d, f = calculate_discount_amount("fixed", Decimal("500"), Decimal("300"))
    assert d == Decimal("300.00") and f == Decimal("0.00")


def test_percentage_10_percent():
    d, f = calculate_discount_amount("percentage", Decimal("10"), Decimal("1000"))
    assert d == Decimal("100.00") and f == Decimal("900.00")


def test_percentage_rounding_half_up():
    # 18% of 99.99 = 17.9982 → rounds to 18.00
    d, f = calculate_discount_amount("percentage", Decimal("18"), Decimal("99.99"))
    assert d == Decimal("18.00") and f == Decimal("81.99")


def test_percentage_small_rounding():
    # 5% of 33.33 = 1.6665 → rounds to 1.67
    d, f = calculate_discount_amount("percentage", Decimal("5"), Decimal("33.33"))
    assert d == Decimal("1.67") and f == Decimal("31.66")


# ===========================================================================
# 3. Service-layer CRUD + business logic
# ===========================================================================

def test_create_and_retrieve_discount(db_session):
    """Create a discount and verify it can be fetched by ID."""
    created = create_discount(db_session, _schema("SVC_CREATE"))
    assert created.id is not None
    assert created.code == "SVC_CREATE"
    assert created.usage_count == 0

    fetched = get_discount_by_id(db_session, created.id)
    assert fetched.id == created.id
    assert fetched.name == "Test Discount"


def test_update_discount(db_session):
    """Partial update of discount fields."""
    created = create_discount(db_session, _schema("SVC_UPD1"))
    updated = update_discount(db_session, created.id, DiscountUpdate(name="Updated Name"))
    assert updated.name == "Updated Name"
    assert updated.code == "SVC_UPD1"  # unchanged


def test_toggle_status(db_session):
    """Activate and deactivate a discount."""
    d = create_discount(db_session, _schema("SVC_TOGGLE"))
    updated = update_discount_status(db_session, d.id, DiscountStatusUpdate(is_active=False))
    assert updated.is_active is False
    reactivated = update_discount_status(db_session, d.id, DiscountStatusUpdate(is_active=True))
    assert reactivated.is_active is True


def test_soft_delete_discount(db_session):
    """Soft-delete deactivates without removing the row."""
    d = create_discount(db_session, _schema("SVC_SDEL"))
    result = delete_discount(db_session, d.id, hard_delete=False)
    assert "deactivated" in result["detail"].lower()
    # Row still exists but is_active=False
    still_there = get_discount_by_id(db_session, d.id)
    assert still_there.is_active is False


def test_validate_valid_code(db_session):
    """Valid discount code returns correct amounts."""
    create_discount(db_session, _schema("SVC_VALID10"))
    r = validate_discount_code(db_session, "SVC_VALID10", Decimal("500.00"))
    assert r.is_valid is True
    assert r.discount_amount == Decimal("50.00")
    assert r.final_amount == Decimal("450.00")


def test_validate_does_not_increment_usage(db_session):
    """Calling validate multiple times must not change usage_count."""
    d = create_discount(db_session, _schema("SVC_NOINCR"))
    validate_discount_code(db_session, "SVC_NOINCR", Decimal("200.00"))
    validate_discount_code(db_session, "SVC_NOINCR", Decimal("200.00"))
    assert get_discount_by_id(db_session, d.id).usage_count == 0


def test_apply_increments_usage(db_session):
    """apply_discount increments usage_count by 1."""
    d = create_discount(db_session, _schema("SVC_APPLY"))
    r = apply_discount(db_session, "SVC_APPLY", Decimal("300.00"))
    assert r.is_valid is True
    assert get_discount_by_id(db_session, d.id).usage_count == 1


def test_expired_code_rejected(db_session):
    """Expired discount code returns is_valid=False with 'expired' message."""
    create_discount(db_session, _schema("SVC_EXPRD", start_date=_past(10), expiry_date=_past(1)))
    r = validate_discount_code(db_session, "SVC_EXPRD", Decimal("300.00"))
    assert r.is_valid is False
    assert "expired" in r.message.lower()


def test_inactive_code_rejected(db_session):
    """Inactive discount code is rejected."""
    create_discount(db_session, _schema("SVC_INACTV", is_active=False))
    r = validate_discount_code(db_session, "SVC_INACTV", Decimal("300.00"))
    assert r.is_valid is False
    assert "inactive" in r.message.lower()


def test_minimum_purchase_not_met(db_session):
    """Discount with minimum purchase requirement rejects low amounts."""
    create_discount(db_session, _schema("SVC_MINREQ", minimum_purchase_amount=Decimal("500.00")))
    r = validate_discount_code(db_session, "SVC_MINREQ", Decimal("100.00"))
    assert r.is_valid is False
    assert "minimum" in r.message.lower()


def test_usage_limit_enforcement(db_session):
    """Once usage_limit is reached, validate rejects the code."""
    create_discount(db_session, _schema("SVC_LIMIT1", usage_limit=1))
    # Consume the single slot via apply
    apply_discount(db_session, "SVC_LIMIT1", Decimal("300.00"))
    # Next validate should fail
    r = validate_discount_code(db_session, "SVC_LIMIT1", Decimal("300.00"))
    assert r.is_valid is False
    assert "usage limit" in r.message.lower()


def test_apply_respects_usage_limit(db_session):
    """apply_discount obeys usage_limit — 3 applies succeed, 4th fails."""
    create_discount(db_session, _schema("SVC_MLIMIT", usage_limit=3))
    for _ in range(3):
        r = apply_discount(db_session, "SVC_MLIMIT", Decimal("500.00"))
        assert r.is_valid is True
    r_over = apply_discount(db_session, "SVC_MLIMIT", Decimal("500.00"))
    assert r_over.is_valid is False


def test_scoped_discount_requires_selected_product(db_session):
    product = Product(
        name="Discount test product",
        product_type="service",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("0.00"),
    )
    db_session.add(product)
    db_session.flush()

    discount = create_discount(
        db_session,
        _schema("SVC_SCOPED", applicable_product_ids=[product.id]),
    )

    result = validate_discount_code(db_session, discount.code, Decimal("100.00"))

    assert result.is_valid is False
    assert "product must be selected" in result.message.lower()
    assert get_discount_by_id(db_session, discount.id).usage_count == 0


def test_apply_scoped_discount_checks_selected_product(db_session):
    product = Product(
        name="Discount test product",
        product_type="service",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("0.00"),
    )
    other_product = Product(
        name="Other discount test product",
        product_type="service",
        sales_price=Decimal("100.00"),
        cost_price=Decimal("0.00"),
    )
    db_session.add_all([product, other_product])
    db_session.flush()
    discount = create_discount(
        db_session,
        _schema("SVC_SCOPED_APPLY", applicable_product_ids=[product.id]),
    )

    rejected = apply_discount(
        db_session, discount.code, Decimal("100.00"), product_id=other_product.id
    )
    assert rejected.is_valid is False
    assert get_discount_by_id(db_session, discount.id).usage_count == 0

    accepted = apply_discount(
        db_session, discount.code, Decimal("100.00"), product_id=product.id
    )
    assert accepted.is_valid is True
    assert get_discount_by_id(db_session, discount.id).usage_count == 1


def test_fixed_discount_correct_amount(db_session):
    """Fixed discount deducts correct flat amount."""
    create_discount(db_session, _schema("SVC_FIXED50", discount_type="fixed", discount_value=Decimal("50")))
    r = validate_discount_code(db_session, "SVC_FIXED50", Decimal("200.00"))
    assert r.is_valid is True
    assert r.discount_amount == Decimal("50.00")
    assert r.final_amount == Decimal("150.00")


def test_invalid_code_returns_not_valid(db_session):
    """Non-existent discount code returns is_valid=False."""
    r = validate_discount_code(db_session, "DOESNOTEXIST", Decimal("300.00"))
    assert r.is_valid is False
