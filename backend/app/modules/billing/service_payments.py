"""PaymentService — recording, voiding, invoice reconciliation (doc §6.C)."""

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.time import utc_now
from . import repository as repo
from .models import Invoice, Payment
from .numbering import allocate_number


class PaymentService:
    def record_payment(
        self,
        session: Session,
        *,
        invoice_id: uuid.UUID,
        amount: Decimal,
        method: str,
        paid_at: dt.datetime | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> tuple[Payment, bool]:
        """Returns (payment, created). A repeated idempotency_key returns the
        existing payment with created=False — safe retries / double-submits."""
        if idempotency_key:
            existing = repo.get_payment_by_key(session, idempotency_key)
            if existing is not None:
                return existing, False

        invoice = repo.get_invoice_for_update(session, invoice_id)
        if invoice is None:
            raise AppError("INVOICE_NOT_FOUND", "Invoice not found", 404)
        if invoice.status != "confirmed":
            raise AppError(
                "INVOICE_NOT_PAYABLE",
                f"Payments require a confirmed invoice (status={invoice.status})",
                409,
            )

        outstanding = invoice.total_amount - invoice.amount_paid
        if amount > outstanding:
            raise AppError(
                "OVERPAYMENT",
                f"Amount {amount} exceeds outstanding balance {outstanding}",
                400,
                details={"outstanding": str(outstanding)},
            )

        paid_at = paid_at or utc_now()
        payment = Payment(
            payment_reference=allocate_number(session, "payment", paid_at.year),
            invoice_id=invoice.id,
            amount=amount,
            method=method,
            status="posted",
            paid_at=paid_at,
            notes=notes,
            idempotency_key=idempotency_key,
            recorded_by=actor_id,
        )
        session.add(payment)

        invoice.amount_paid = invoice.amount_paid + amount
        if invoice.amount_paid >= invoice.total_amount:
            invoice.status = "paid"

        session.flush()
        return payment, True

    def void_payment(
        self,
        session: Session,
        payment_id: uuid.UUID,
        *,
        reason: str,
        actor_id: uuid.UUID | None = None,
    ) -> Payment:
        payment = repo.get_payment(session, payment_id)
        if payment is None:
            raise AppError("PAYMENT_NOT_FOUND", "Payment not found", 404)
        if payment.status == "voided":
            raise AppError("INVALID_STATE", "Payment already voided", 409)

        invoice = repo.get_invoice_for_update(session, payment.invoice_id)
        payment.status = "voided"
        payment.voided_at = utc_now()
        payment.void_reason = reason

        if invoice is not None:
            invoice.amount_paid = invoice.amount_paid - payment.amount
            if invoice.status == "paid" and invoice.amount_paid < invoice.total_amount:
                invoice.status = "confirmed"

        session.flush()
        return payment
