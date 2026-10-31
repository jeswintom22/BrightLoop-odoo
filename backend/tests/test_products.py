import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.db.session import SessionLocal
from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.product_variant import ProductVariantCreate, ProductVariantUpdate


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_product_validation_errors():
    """Verify validations: name required, prices non-negative, valid product type."""
    # Blank name
    with pytest.raises(ValidationError):
        ProductCreate(
            name="   ",
            product_type="goods",
            sales_price=Decimal("100.00"),
            cost_price=Decimal("50.00")
        )

    # Negative price
    with pytest.raises(ValidationError):
        ProductCreate(
            name="Laptop",
            product_type="goods",
            sales_price=Decimal("-10.00"),
            cost_price=Decimal("50.00")
        )

    # Invalid product type
    with pytest.raises(ValidationError):
        ProductCreate(
            name="Laptop",
            product_type="unknown_category",
            sales_price=Decimal("100.00"),
            cost_price=Decimal("50.00")
        )


def test_product_crud_and_variants(db_session):
    """Test full product lifecycle and variant associations."""
    # 1. Create Product
    product_in = ProductCreate(
        name="Cloud ERP Subscription",
        product_type="service",
        sales_price=Decimal("199.99"),
        cost_price=Decimal("50.00"),
        notes="Monthly enterprise service",
        is_active=True
    )
    product = ProductService.create_product(db_session, product_in)
    assert product.id is not None
    assert product.name == "Cloud ERP Subscription"
    assert product.sales_price == Decimal("199.99")
    product_id = product.id

    # 2. Add Variants
    v1_in = ProductVariantCreate(
        name="Enterprise Tier (10 Seats)",
        sku="ERP-ENT-10",
        sales_price=Decimal("499.00"),
        cost_price=Decimal("100.00"),
        attributes={"tier": "enterprise", "seats": 10}
    )
    variant1 = ProductService.create_variant(db_session, product_id, v1_in)
    assert variant1 is not None
    assert variant1.id is not None
    assert variant1.product_id == product_id
    assert variant1.sku == "ERP-ENT-10"

    v2_in = ProductVariantCreate(
        name="Pro Tier (5 Seats)",
        sku="ERP-PRO-5",
        sales_price=Decimal("299.00"),
        cost_price=Decimal("70.00"),
        attributes={"tier": "pro", "seats": 5}
    )
    variant2 = ProductService.create_variant(db_session, product_id, v2_in)
    assert variant2 is not None

    # 3. Read Product with Variants
    fetched = ProductService.get_product_by_id(db_session, product_id)
    assert fetched is not None
    assert len(fetched.variants) == 2

    # 4. Filter & Search Products
    items, total, pages = ProductService.get_products(
        db_session, search="Cloud ERP", product_type="service"
    )
    assert total >= 1
    assert any(p.id == product_id for p in items)

    # 5. Update Variant
    updated_v = ProductService.update_variant(
        db_session, variant1.id, ProductVariantUpdate(sales_price=Decimal("550.00"))
    )
    assert updated_v.sales_price == Decimal("550.00")

    # 6. Update Product
    updated_p = ProductService.update_product(
        db_session, product_id, ProductUpdate(notes="Updated enterprise service notes")
    )
    assert updated_p.notes == "Updated enterprise service notes"

    # 7. Delete Variant
    assert ProductService.delete_variant(db_session, variant2.id) is True
    assert ProductService.get_variant_by_id(db_session, variant2.id) is None

    # 8. Delete Product (Cascades to remaining variants)
    v1_id = variant1.id
    assert ProductService.delete_product(db_session, product_id) is True
    assert ProductService.get_product_by_id(db_session, product_id) is None
    # Variant 1 must also be deleted
    assert ProductService.get_variant_by_id(db_session, v1_id) is None
