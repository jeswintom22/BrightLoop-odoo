from decimal import Decimal

import pytest

from app.core.errors import AppError


def test_full_payment_marks_invoice_paid(
    payment_service, session, confirmed_invoice
):
    payment, created = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=confirmed_invoice.total_amount,
        method="upi",
    )
    session.commit()
    assert created is True
    assert payment.payment_reference.startswith("PAY-")
    assert payment.status == "posted"
    assert confirmed_invoice.amount_paid == confirmed_invoice.total_amount
    assert confirmed_invoice.status == "paid"
    assert confirmed_invoice.outstanding == Decimal("0")


def test_partial_payment_keeps_confirmed(
    payment_service, session, confirmed_invoice
):
    payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("100.00"),
        method="cash",
    )
    session.commit()
    assert confirmed_invoice.status == "confirmed"
    assert confirmed_invoice.amount_paid == Decimal("100.00")
    assert confirmed_invoice.outstanding == confirmed_invoice.total_amount - Decimal(
        "100.00"
    )


def test_overpayment_rejected(payment_service, session, confirmed_invoice):
    payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("100.00"),
        method="card",
    )
    with pytest.raises(AppError) as exc:
        payment_service.record_payment(
            session,
            invoice_id=confirmed_invoice.id,
            amount=confirmed_invoice.total_amount,  # exceeds remaining
            method="card",
        )
    assert exc.value.code == "OVERPAYMENT"


def test_payment_on_draft_rejected(payment_service, session, billing, providers):
    from app.core.time import business_date

    sub = providers["subs"].get_due_subscriptions(business_date(), limit=1)[0]
    draft, _ = billing.generate_invoice(session, subscription_id=sub.id)
    session.commit()

    with pytest.raises(AppError) as exc:
        payment_service.record_payment(
            session, invoice_id=draft.id, amount=Decimal("10"), method="upi"
        )
    assert exc.value.code == "INVOICE_NOT_PAYABLE"


def test_idempotency_key_returns_same_payment(
    payment_service, session, confirmed_invoice
):
    first, created1 = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("50.00"),
        method="bank_transfer",
        idempotency_key="retry-abc",
    )
    session.commit()
    second, created2 = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("50.00"),
        method="bank_transfer",
        idempotency_key="retry-abc",
    )
    assert created1 is True
    assert created2 is False
    assert second.id == first.id
    # balance moved once, not twice
    assert confirmed_invoice.amount_paid == Decimal("50.00")


def test_void_payment_reverses_balance(
    payment_service, session, confirmed_invoice
):
    payment, _ = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=confirmed_invoice.total_amount,
        method="upi",
    )
    session.commit()
    assert confirmed_invoice.status == "paid"

    payment_service.void_payment(session, payment.id, reason="duplicate entry")
    session.commit()
    assert payment.status == "voided"
    assert payment.void_reason == "duplicate entry"
    assert confirmed_invoice.amount_paid == Decimal("0")
    assert confirmed_invoice.status == "confirmed"


def test_void_twice_rejected(payment_service, session, confirmed_invoice):
    payment, _ = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("10"),
        method="cash",
    )
    session.commit()
    payment_service.void_payment(session, payment.id, reason="mistake")
    with pytest.raises(AppError) as exc:
        payment_service.void_payment(session, payment.id, reason="again")
    assert exc.value.code == "INVALID_STATE"


def test_cancel_invoice_with_payments_rejected(
    payment_service, session, billing, confirmed_invoice
):
    payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("10"),
        method="cash",
    )
    session.commit()
    with pytest.raises(AppError) as exc:
        billing.cancel_invoice(session, confirmed_invoice)
    assert exc.value.code == "INVALID_STATE"


def test_idempotent_retry_same_payload(payment_service, session, confirmed_invoice):
    p1, created1 = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("50"),
        method="upi",
        idempotency_key="pay-abc-1",
    )
    session.commit()
    p2, created2 = payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("50"),
        method="upi",
        idempotency_key="pay-abc-1",
    )
    assert created1 is True
    assert created2 is False
    assert p2.id == p1.id


def test_idempotency_key_reused_different_amount_conflicts(
    payment_service, session, confirmed_invoice
):
    payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("50"),
        method="upi",
        idempotency_key="pay-abc-2",
    )
    session.commit()
    with pytest.raises(AppError) as exc:
        payment_service.record_payment(
            session,
            invoice_id=confirmed_invoice.id,
            amount=Decimal("75"),
            method="upi",
            idempotency_key="pay-abc-2",
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"


def test_idempotency_key_reused_different_invoice_conflicts(
    payment_service, session, billing, providers, confirmed_invoice
):
    from app.core.time import business_date

    payment_service.record_payment(
        session,
        invoice_id=confirmed_invoice.id,
        amount=Decimal("50"),
        method="upi",
        idempotency_key="pay-abc-3",
    )
    # second confirmed invoice for a different subscription
    sub2 = providers["subs"].get_due_subscriptions(business_date(), limit=10)[1]
    inv2, _ = billing.generate_invoice(session, subscription_id=sub2.id)
    billing.confirm_invoice(session, inv2)
    session.commit()
    with pytest.raises(AppError) as exc:
        payment_service.record_payment(
            session,
            invoice_id=inv2.id,
            amount=Decimal("50"),
            method="upi",
            idempotency_key="pay-abc-3",
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
