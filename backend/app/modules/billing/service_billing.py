"""BillingService — invoice generation + recurring billing runs.

Architecture doc §6.A/§6.B. Invoice lines are immutable price snapshots taken
from the P2 pricing contract at generation time.
"""

import datetime as dt
import uuid
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ...core.config import get_settings
from ...core.errors import AppError
from ...core.time import business_date, utc_now
from . import repository as repo
from .integrations import (
    CustomerProvider,
    PricingProvider,
    SubscriptionProvider,
)
from .models import BillingRun, Invoice, InvoiceLine
from .numbering import allocate_number

CENTS = Decimal("0.01")
DEFAULT_DUE_DAYS = 7  # [PROPOSED] invoice payment terms — team decision

FREQ_DELTA = {
    "daily": relativedelta(days=1),
    "weekly": relativedelta(weeks=1),
    "monthly": relativedelta(months=1),
    "yearly": relativedelta(years=1),
}


class BillingService:
    def __init__(
        self,
        *,
        pricing: PricingProvider,
        subscriptions: SubscriptionProvider,
        customers: CustomerProvider,
    ):
        self.pricing = pricing
        self.subscriptions = subscriptions
        self.customers = customers

    # --- period math -----------------------------------------------------------

    @staticmethod
    def period_end_for(start: dt.date, frequency: str) -> dt.date:
        delta = FREQ_DELTA.get(frequency)
        if delta is None:
            raise AppError(
                "INVALID_FREQUENCY",
                f"Unknown billing frequency: {frequency}",
                400,
            )
        return start + delta

    # --- invoice generation -----------------------------------------------------

    def generate_invoice(
        self,
        session: Session,
        *,
        subscription_id: uuid.UUID,
        period_start: dt.date | None = None,
        period_end: dt.date | None = None,
        due_date: dt.date | None = None,
        run_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> tuple[Invoice, bool]:
        """Returns (invoice, created). On (subscription, period) conflict,
        returns the existing invoice with created=False — idempotent."""
        view = self.subscriptions.get_subscription_view(subscription_id)
        if view is None:
            raise AppError("SUBSCRIPTION_NOT_FOUND", "Subscription not found", 404)
        if view.status != "active":
            raise AppError(
                "SUBSCRIPTION_NOT_BILLABLE",
                f"Subscription status is '{view.status}'",
                409,
            )

        period_start = period_start or view.next_billing_date
        period_end = period_end or self.period_end_for(period_start, view.billing_frequency)

        if view.expiry_date is not None and view.expiry_date < period_start:
            raise AppError(
                "SUBSCRIPTION_NOT_BILLABLE",
                "Subscription expired before this billing period",
                409,
            )

        issue_date = business_date()
        invoice = Invoice(
            invoice_number=allocate_number(session, "invoice", issue_date.year),
            subscription_id=view.id,
            customer_id=view.customer_id,
            status="draft",
            issue_date=issue_date,
            due_date=due_date or issue_date + dt.timedelta(days=DEFAULT_DUE_DAYS),
            period_start=period_start,
            period_end=period_end,
            currency=get_settings().DEFAULT_CURRENCY,
            subtotal=Decimal("0"),
            tax_total=Decimal("0"),
            discount_total=Decimal("0"),
            total_amount=Decimal("0"),
            billing_run_id=run_id,
            created_by=actor_id,
        )

        subtotal = tax_total = discount_total = Decimal("0")
        for position, sline in enumerate(view.lines):
            price = self.pricing.price_line(
                sline.product_id, sline.quantity, customer_id=view.customer_id
            )
            invoice.lines.append(
                InvoiceLine(
                    product_id=sline.product_id,
                    subscription_line_id=sline.subscription_line_id,
                    description=sline.description,
                    position=position,
                    quantity=sline.quantity,
                    unit_price=price.unit_price,
                    subtotal=price.subtotal,
                    tax_amount=price.tax_total,
                    discount_amount=price.discount_total,
                    line_total=price.line_total,
                    meta={
                        "tax_details": price.tax_details,
                        "discount_details": price.discount_details,
                    },
                )
            )
            subtotal += price.subtotal
            tax_total += price.tax_total
            discount_total += price.discount_total

        invoice.subtotal = subtotal.quantize(CENTS)
        invoice.tax_total = tax_total.quantize(CENTS)
        invoice.discount_total = discount_total.quantize(CENTS)
        invoice.total_amount = (
            subtotal + tax_total - discount_total
        ).quantize(CENTS)

        try:
            with session.begin_nested():  # savepoint — survives outer rollback
                session.add(invoice)
                session.flush()
                # P3 contract: advance inside the SAME transaction so an
                # invoice can never exist without the date moving (and vice
                # versa — a rollback undoes both).
                self.subscriptions.advance_billing_date(
                    session, subscription_id, period_end
                )
        except IntegrityError:
            existing = repo.get_invoice_by_period(
                session, subscription_id, period_start, period_end
            )
            if existing is not None:
                return existing, False
            raise

        return invoice, True

    def confirm_invoice(self, session: Session, invoice: Invoice) -> Invoice:
        if invoice.status != "draft":
            raise AppError(
                "INVALID_STATE",
                f"Only draft invoices can be confirmed (status={invoice.status})",
                409,
            )
        invoice.status = "confirmed"
        invoice.confirmed_at = utc_now()
        session.flush()
        return invoice

    def cancel_invoice(self, session: Session, invoice: Invoice) -> Invoice:
        if invoice.status == "cancelled":
            raise AppError("INVALID_STATE", "Invoice already cancelled", 409)
        if invoice.amount_paid and invoice.amount_paid > 0:
            raise AppError(
                "INVALID_STATE",
                "Cannot cancel an invoice with posted payments — void them first",
                409,
            )
        invoice.status = "cancelled"
        invoice.cancelled_at = utc_now()
        session.flush()
        return invoice

    def patch_draft(
        self,
        session: Session,
        invoice: Invoice,
        *,
        due_date: dt.date | None,
        notes: str | None,
    ) -> Invoice:
        if invoice.status != "draft":
            raise AppError(
                "INVALID_STATE", "Only draft invoices can be edited", 409
            )
        if due_date is not None:
            invoice.due_date = due_date
        if notes is not None:
            invoice.notes = notes
        session.flush()
        return invoice

    # --- recurring billing runs --------------------------------------------------

    def execute_run(
        self,
        session_factory: sessionmaker,
        *,
        run_for_date: dt.date | None = None,
        limit: int = 200,
        offset: int = 0,
        trigger: str = "manual",
        actor_id: uuid.UUID | None = None,
    ) -> BillingRun:
        """Per-subscription transactions isolate failures; the unique
        (subscription, period) constraint makes the run fully re-entrant."""
        run_for_date = run_for_date or business_date()

        with session_factory() as run_session:
            run = BillingRun(
                trigger_source=trigger,
                requested_by=actor_id,
                run_for_date=run_for_date,
                status="running",
                started_at=utc_now(),
            )
            run_session.add(run)
            run_session.commit()

            errors: list[dict] = []
            try:
                run.closed = self.subscriptions.close_expired(
                    run_session, run_for_date
                )
                due = self.subscriptions.get_due_subscriptions(
                    run_for_date, limit=limit, offset=offset
                )
                run.scanned = len(due)
                for view in due:
                    try:
                        with session_factory() as s:
                            _, created = self.generate_invoice(
                                s,
                                subscription_id=view.id,
                                run_id=run.id,
                                actor_id=actor_id,
                            )
                            s.commit()
                        if created:
                            run.generated += 1
                        else:
                            run.skipped += 1
                    except Exception as exc:  # isolate per-subscription failures
                        run.failed += 1
                        errors.append(
                            {
                                "subscription_id": str(view.id),
                                "message": f"{type(exc).__name__}: {exc}",
                            }
                        )
            except Exception as exc:
                errors.append({"message": f"{type(exc).__name__}: {exc}"})

            if run.failed and run.generated == 0 and run.scanned > 0:
                run.status = "failed"
            elif run.failed:
                run.status = "partial"
            else:
                run.status = "success"
            run.errors = errors or None
            run.finished_at = utc_now()
            run_session.commit()
            return run
