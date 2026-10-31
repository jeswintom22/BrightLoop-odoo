import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.db.session import SessionLocal
from app.services.tax_service import TaxService
from app.schemas.tax import TaxCreate, TaxUpdate, TaxCalculationRequest


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_tax_schema_validations():
    """Verify validation for tax percentage ranges and names."""
    # Blank name
    with pytest.raises(ValidationError):
        TaxCreate(name="   ", tax_percentage=Decimal("18.00"))

    # Negative tax percentage
    with pytest.raises(ValidationError):
        TaxCreate(name="GST", tax_percentage=Decimal("-5.00"))

    # Greater than 100% tax
    with pytest.raises(ValidationError):
        TaxCreate(name="Luxury", tax_percentage=Decimal("105.00"))


def test_tax_calculation_pure_logic():
    """Verify monetary math using Python Decimal with standard rounding."""
    # Example 1: 1000 with 18% tax -> tax = 180.00, final = 1180.00
    res1 = TaxService.calculate_tax(Decimal("1000.00"), Decimal("18.00"))
    assert res1.taxable_amount == Decimal("1000.00")
    assert res1.tax_percentage == Decimal("18.00")
    assert res1.tax_amount == Decimal("180.00")
    assert res1.final_amount == Decimal("1180.00")

    # Example 2: Zero-rated tax (0.00%)
    res2 = TaxService.calculate_tax(Decimal("500.00"), Decimal("0.00"))
    assert res2.tax_amount == Decimal("0.00")
    assert res2.final_amount == Decimal("500.00")

    # Example 3: Fractional rounding (ROUND_HALF_UP)
    # 99.99 * 18% = 17.9982 -> rounded to 18.00; total = 117.99
    res3 = TaxService.calculate_tax(Decimal("99.99"), Decimal("18.00"))
    assert res3.tax_amount == Decimal("18.00")
    assert res3.final_amount == Decimal("117.99")

    # Negative taxable amount rejected
    with pytest.raises(ValueError):
        TaxService.calculate_tax(Decimal("-100.00"), Decimal("18.00"))

    # Invalid tax percentage rejected
    with pytest.raises(ValueError):
        TaxService.calculate_tax(Decimal("100.00"), Decimal("101.00"))


def test_tax_crud_and_calculation_via_db(db_session):
    """Verify tax database CRUD and calculation via registered tax_id."""
    # 1. Create Tax Configuration
    tax_in = TaxCreate(
        name="GST Standard 18%",
        tax_percentage=Decimal("18.00"),
        description="Standard Indian Goods and Services Tax",
        is_active=True,
    )
    tax = TaxService.create_tax(db_session, tax_in)
    assert tax.id is not None
    assert tax.name == "GST Standard 18%"
    tax_id = tax.id

    # 2. Get by ID
    fetched = TaxService.get_tax_by_id(db_session, tax_id)
    assert fetched is not None
    assert fetched.tax_percentage == Decimal("18.00")

    # 3. Calculate Tax via tax_id
    calc_req = TaxCalculationRequest(taxable_amount=Decimal("1000.00"), tax_id=tax_id)
    calc_res = TaxService.calculate_tax_for_request(db_session, calc_req)
    assert calc_res.tax_amount == Decimal("180.00")
    assert calc_res.final_amount == Decimal("1180.00")
    assert calc_res.tax_name == "GST Standard 18%"

    # 4. Update Tax
    updated = TaxService.update_tax(
        db_session, tax_id, TaxUpdate(name="GST Reduced 12%", tax_percentage=Decimal("12.00"))
    )
    assert updated.tax_percentage == Decimal("12.00")

    # 5. Deactivate Tax & verify rejection on inactive calculation
    TaxService.update_tax_status(db_session, tax_id, is_active=False)
    with pytest.raises(ValueError, match="is currently inactive"):
        TaxService.calculate_tax_for_request(db_session, calc_req)

    # 6. Delete Tax
    assert TaxService.delete_tax(db_session, tax_id, hard_delete=True) is True
    assert TaxService.get_tax_by_id(db_session, tax_id) is None
