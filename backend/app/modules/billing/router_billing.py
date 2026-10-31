import datetime as dt

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, sessionmaker

from ...core.config import Settings, get_settings
from ...core.pagination import Page, paginate
from ...core.time import business_date
from ...deps import (
    CurrentUser,
    get_billing_service,
    get_customer_provider,
    get_db,
    get_session_factory,
    get_subscription_provider,
    require_roles,
)
from ...services.notification_event_service import notify_billing_run_invoices
from .integrations import CustomerProvider, SubscriptionProvider
from .models import BillingRun
from .schemas import (
    BillingRunOut,
    BillingRunRequest,
    BillingRunResult,
    DueSubscriptionOut,
)
from .service_billing import BillingService

router = APIRouter(tags=["billing"])

READ = Depends(require_roles("admin", "staff"))
WRITE = Depends(require_roles("admin", "staff"))


def _run_result(run: BillingRun, remaining: int) -> BillingRunResult:
    data = BillingRunOut.model_validate(run).model_dump()
    data["remaining"] = remaining
    return BillingRunResult.model_validate(data)


@router.post("/billing/runs", response_model=BillingRunResult)
def trigger_billing_run(
    body: BillingRunRequest,
    service: BillingService = Depends(get_billing_service),
    subscriptions: SubscriptionProvider = Depends(get_subscription_provider),
    session_factory: sessionmaker = Depends(get_session_factory),
    customers: CustomerProvider = Depends(get_customer_provider),
    settings: Settings = Depends(get_settings),
    user: CurrentUser = WRITE,
):
    run_for_date = body.run_for_date or business_date()
    run = service.execute_run(
        session_factory,
        run_for_date=run_for_date,
        limit=body.limit,
        offset=body.offset,
        trigger="manual",
        actor_id=user.id,
    )
    notify_billing_run_invoices(
        session_factory, run=run, customers=customers, settings=settings
    )
    return _run_result(run, subscriptions.count_due(run_for_date))


@router.get("/billing/runs", response_model=Page[BillingRunOut])
def list_billing_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    stmt = sa.select(BillingRun).order_by(BillingRun.started_at.desc())
    items, total = paginate(session, stmt, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/billing/due", response_model=list[DueSubscriptionOut])
def due_preview(
    as_of: dt.date | None = None,
    limit: int = Query(200, ge=1, le=1000),
    subscriptions: SubscriptionProvider = Depends(get_subscription_provider),
    customers: CustomerProvider = Depends(get_customer_provider),
    _user: CurrentUser = READ,
):
    due = subscriptions.get_due_subscriptions(as_of or business_date(), limit=limit)
    names = customers.get_many([v.customer_id for v in due])
    return [
        DueSubscriptionOut(
            subscription_id=v.id,
            customer_id=v.customer_id,
            customer_name=(
                names[v.customer_id].name if v.customer_id in names else None
            ),
            billing_frequency=v.billing_frequency,
            next_billing_date=v.next_billing_date,
            expiry_date=v.expiry_date,
            line_count=len(v.lines),
        )
        for v in due
    ]
