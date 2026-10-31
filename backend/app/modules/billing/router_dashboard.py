import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...deps import (
    CurrentUser,
    get_customer_provider,
    get_db,
    get_subscription_provider,
    require_roles,
)
from . import service_dashboard
from .integrations import CustomerProvider, SubscriptionProvider
from .schemas import DashboardSummary, RevenueTrendOut

router = APIRouter(tags=["dashboard"])

READ = Depends(require_roles("admin", "staff"))


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    session: Session = Depends(get_db),
    subscriptions: SubscriptionProvider = Depends(get_subscription_provider),
    customers: CustomerProvider = Depends(get_customer_provider),
    _user: CurrentUser = READ,
):
    return service_dashboard.summary(
        session,
        subscriptions,
        customers,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/dashboard/revenue-trend", response_model=RevenueTrendOut)
def revenue_trend(
    interval: str = Query("month", pattern="^(day|week|month)$"),
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    return service_dashboard.revenue_trend(
        session, interval=interval, date_from=date_from, date_to=date_to
    )
