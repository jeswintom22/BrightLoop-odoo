"""Internal endpoints — shared-secret auth, for GitHub Actions only.
Not exposed in the public OpenAPI schema."""

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, sessionmaker

from ...core.config import Settings, get_settings
from ...core.database import get_db
from ...core.errors import AppError
from ...core.time import business_date
from ...deps import (
    get_customer_provider,
    get_billing_service,
    get_pricing_provider,
    get_session_factory,
    get_subscription_provider,
    verify_internal_token,
)
from ...services.notification_event_service import notify_billing_run_invoices
from ...services.notification_scheduler_service import (
    process_scheduled_notifications,
    retry_due_notifications,
)
from .integrations import CustomerProvider, PricingProvider, SubscriptionProvider
from .schemas import BillingRunOut, BillingRunRequest, BillingRunResult
from .service_billing import BillingService

router = APIRouter(
    prefix="/internal",
    dependencies=[Depends(verify_internal_token)],
    include_in_schema=False,
)


@router.post("/billing/run", response_model=BillingRunResult)
def scheduled_billing_run(
    body: BillingRunRequest,
    service: BillingService = Depends(get_billing_service),
    subscriptions: SubscriptionProvider = Depends(get_subscription_provider),
    session_factory: sessionmaker = Depends(get_session_factory),
    customers: CustomerProvider = Depends(get_customer_provider),
    settings: Settings = Depends(get_settings),
):
    run_for_date: dt.date = body.run_for_date or business_date()
    run = service.execute_run(
        session_factory,
        run_for_date=run_for_date,
        limit=body.limit,
        offset=body.offset,
        trigger="scheduled",
    )
    notify_billing_run_invoices(
        session_factory, run=run, customers=customers, settings=settings
    )
    data = BillingRunOut.model_validate(run).model_dump()
    data["remaining"] = subscriptions.count_due(run_for_date)
    return BillingRunResult.model_validate(data)


@router.post("/notifications/run")
def scheduled_notifications_run(
    run_for_date: dt.date | None = Query(None),
    batch_size: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    customers: CustomerProvider = Depends(get_customer_provider),
    subscriptions: SubscriptionProvider = Depends(get_subscription_provider),
    pricing: PricingProvider = Depends(get_pricing_provider),
    settings: Settings = Depends(get_settings),
):
    if settings.ENVIRONMENT.lower() in {"prod", "production"} and any(
        getattr(provider, "is_stub_provider", False)
        for provider in (customers, subscriptions, pricing)
    ):
        raise AppError(
            "NOTIFICATION_PROVIDERS_NOT_CONFIGURED",
            "Scheduled notifications require production customer, subscription, and pricing providers",
            503,
        )
    return process_scheduled_notifications(
        db,
        customers=customers,
        subscriptions=subscriptions,
        pricing=pricing,
        settings=settings,
        as_of=run_for_date or business_date(),
        batch_size=batch_size,
    )


@router.post("/notifications/retries")
def scheduled_notification_retries(
    batch_size: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return retry_due_notifications(db, settings=settings, batch_size=batch_size)
