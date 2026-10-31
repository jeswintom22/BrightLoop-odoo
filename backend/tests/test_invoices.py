from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.core.time import business_date
from app.modules.billing.service_billing import BillingService


def _due_sub(providers, n=0):
    return providers["subs"].get_due_subscriptions(business_date(), limit=n + 1)[n]


def test_generate_invoice_snapshots_lines_and_totals(billing, session, providers):
    sub = _due_sub(providers)
    invoice, created = billing.generate_invoice(session, subscription_id=sub.id)
    session.commit()

    assert created is True
    assert invoice.status == "draft"
    assert invoice.invoice_number.startswith("INV-")
    assert len(invoice.lines) == 1

    # Stub pricing: unit 999.00, qty 1, 18% tax
    line = invoice.lines[0]
    assert line.unit_price == Decimal("999.00")
    assert line.tax_amount == Decimal("179.82")
    assert invoice.subtotal == Decimal("999.00")
    assert invoice.tax_total == Decimal("179.82")
    assert invoice.total_amount == Decimal("1178.82")
    assert invoice.amount_paid == Decimal("0")
    assert invoice.outstanding == Decimal("1178.82")


def test_generate_invoice_advances_next_billing_date(billing, session, providers):
    sub = _due_sub(providers)
    before = sub.next_billing_date
    invoice, _ = billing.generate_invoice(session, subscription_id=sub.id)
    session.commit()
    assert sub.next_billing_date == invoice.period_end
    assert invoice.period_end > before


def test_duplicate_period_returns_existing_not_new(billing, session, providers):
    sub = _due_sub(providers)
    first, _ = billing.generate_invoice(session, subscription_id=sub.id)
    session.commit()

    # Same explicit period -> unique constraint -> returns existing invoice
    second, created = billing.generate_invoice(
        session,
        subscription_id=sub.id,
        period_start=first.period_start,
        period_end=first.period_end,
    )
    assert created is False
    assert second.id == first.id


def test_invoice_numbers_are_unique_and_sequential(billing, session, providers):
    subs = providers["subs"].get_due_subscriptions(business_date(), limit=2)
    inv1, _ = billing.generate_invoice(session, subscription_id=subs[0].id)
    inv2, _ = billing.generate_invoice(session, subscription_id=subs[1].id)
    session.commit()
    assert inv1.invoice_number != inv2.invoice_number
    n1 = int(inv1.invoice_number.rsplit("-", 1)[1])
    n2 = int(inv2.invoice_number.rsplit("-", 1)[1])
    assert n2 == n1 + 1


def test_generate_rejects_non_active_subscription(billing, session, providers):
    sub = providers["subs"].all()[0]
    sub.status = "cancelled"
    with pytest.raises(AppError) as exc:
        billing.generate_invoice(session, subscription_id=sub.id)
    assert exc.value.code == "SUBSCRIPTION_NOT_BILLABLE"


def test_generate_rejects_expired_subscription(billing, session, providers):
    import datetime as dt

    sub = providers["subs"].get_due_subscriptions(business_date(), limit=1)[0]
    sub.expiry_date = sub.next_billing_date - dt.timedelta(days=1)
    with pytest.raises(AppError) as exc:
        billing.generate_invoice(session, subscription_id=sub.id)
    assert exc.value.code == "SUBSCRIPTION_NOT_BILLABLE"


def test_confirm_then_cancel_cycle(billing, session, providers):
    sub = _due_sub(providers)
    invoice, _ = billing.generate_invoice(session, subscription_id=sub.id)

    billing.confirm_invoice(session, invoice)
    assert invoice.status == "confirmed"
    assert invoice.confirmed_at is not None

    billing.cancel_invoice(session, invoice)
    assert invoice.status == "cancelled"
    assert invoice.cancelled_at is not None

    with pytest.raises(AppError):
        billing.confirm_invoice(session, invoice)


def test_confirm_on_confirmed_rejected(billing, session, providers):
    sub = _due_sub(providers)
    invoice, _ = billing.generate_invoice(session, subscription_id=sub.id)
    billing.confirm_invoice(session, invoice)
    with pytest.raises(AppError) as exc:
        billing.confirm_invoice(session, invoice)
    assert exc.value.code == "INVALID_STATE"


def test_patch_draft_only(billing, session, providers):
    import datetime as dt

    sub = _due_sub(providers)
    invoice, _ = billing.generate_invoice(session, subscription_id=sub.id)
    new_due = business_date() + dt.timedelta(days=30)
    billing.patch_draft(session, invoice, due_date=new_due, notes="net 30")
    assert invoice.due_date == new_due
    assert invoice.notes == "net 30"

    billing.confirm_invoice(session, invoice)
    with pytest.raises(AppError):
        billing.patch_draft(session, invoice, due_date=new_due, notes=None)


def test_period_end_for_all_frequencies():
    d = business_date()
    for freq in ("daily", "weekly", "monthly", "yearly"):
        assert BillingService.period_end_for(d, freq) > d
    with pytest.raises(AppError):
        BillingService.period_end_for(d, "hourly")
