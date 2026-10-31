"""Internal endpoints — shared-secret auth, for GitHub Actions only.
Not exposed in the public OpenAPI schema."""

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import sessionmaker

from ...core.time import business_date
from ...deps import (
    get_billing_service,
    get_session_factory,
    get_subscription_provider,
    verify_internal_token,
)
from .integrations import SubscriptionProvider
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
):
    run_for_date: dt.date = body.run_for_date or business_date()
    run = service.execute_run(
        session_factory,
        run_for_date=run_for_date,
        limit=body.limit,
        offset=body.offset,
        trigger="scheduled",
    )
    data = BillingRunOut.model_validate(run).model_dump()
    data["remaining"] = subscriptions.count_due(run_for_date)
    return BillingRunResult.model_validate(data)
