from decimal import Decimal

import sqlalchemy as sa

from app.core.time import business_date
from app.modules.billing.models import Invoice
from app.modules.billing.service_billing import BillingService


def test_execute_run_bills_all_due_subscriptions(
    billing, session_factory, providers
):
    run = billing.execute_run(
        session_factory, run_for_date=business_date(), trigger="manual"
    )
    assert run.status == "success"
    # Seed: 4 due (3 monthly + 1 weekly), 1 future, 1 expired
    assert run.scanned == 4
    assert run.generated == 4
    assert run.failed == 0
    assert providers["subs"].count_due(business_date()) == 0


def test_run_is_reentrant_second_run_bills_nothing(
    billing, session_factory, providers
):
    billing.execute_run(session_factory, run_for_date=business_date())
    run2 = billing.execute_run(session_factory, run_for_date=business_date())
    assert run2.scanned == 0
    assert run2.generated == 0
    assert run2.status == "success"


def test_existing_period_invoice_is_skipped_not_duplicated(
    billing, session_factory, session, providers
):
    today = business_date()
    sub = providers["subs"].get_due_subscriptions(today, limit=1)[0]
    period_end = BillingService.period_end_for(
        sub.next_billing_date, sub.billing_frequency
    )
    session.add(
        Invoice(
            invoice_number="INV-MANUAL-1",
            subscription_id=sub.id,
            customer_id=sub.customer_id,
            status="confirmed",
            issue_date=today,
            due_date=today,
            period_start=sub.next_billing_date,
            period_end=period_end,
            currency="INR",
            subtotal=Decimal("0"),
            tax_total=Decimal("0"),
            discount_total=Decimal("0"),
            total_amount=Decimal("0"),
            amount_paid=Decimal("0"),
        )
    )
    session.commit()

    run = billing.execute_run(session_factory, run_for_date=today)
    assert run.generated == 3
    assert run.skipped == 1
    assert run.failed == 0

    # exactly one invoice exists for that (subscription, period)
    count = session.scalar(
        sa.select(sa.func.count(Invoice.id)).where(
            Invoice.subscription_id == sub.id,
            Invoice.period_start == sub.next_billing_date,
            Invoice.period_end == period_end,
        )
    )
    assert count == 1


def test_per_subscription_failure_is_isolated(
    billing, session_factory, providers
):
    from app.modules.billing.integrations_stub import StubPricingProvider
    from app.modules.billing.service_billing import BillingService as BS

    today = business_date()
    victim = providers["subs"].get_due_subscriptions(today, limit=1)[0]

    class FailingPricing(StubPricingProvider):
        def price_line(self, product_id, quantity, customer_id=None):
            if product_id == victim.lines[0].product_id:
                raise RuntimeError("catalog exploded")
            return super().price_line(product_id, quantity, customer_id)

    failing_service = BS(
        pricing=FailingPricing(),
        subscriptions=providers["subs"],
        customers=providers["customers"],
    )
    run = failing_service.execute_run(session_factory, run_for_date=today)
    assert run.scanned == 4
    assert run.generated == 3
    assert run.failed == 1
    assert run.status == "partial"
    assert run.errors
    assert "catalog exploded" in run.errors[0]["message"]
