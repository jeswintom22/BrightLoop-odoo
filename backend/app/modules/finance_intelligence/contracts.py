"""Typed contracts the Finance Copilot consumes from P2 and P3.

Agreed integration surface (in-process service calls in the shared
monolith — no HTTP between modules, per docs/architecture.md §1):

- ``ProductAnalyticsProvider``     — P2's product/pricing/discount analytics.
- ``SubscriptionAnalyticsProvider``— P3's churn/retention/renewal analytics.

Owners may ship their own implementations; until then
``finance_intelligence.integrations`` provides DB-backed implementations that
compute the same DTOs from the shared tables. The copilot only ever sees the
DTOs below — swapping providers requires no copilot changes.
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session


# --- P2: product & discount intelligence -------------------------------------

@dataclass
class ProductRevenueRow:
    product_id: int | None
    product_name: str
    invoiced_revenue: Decimal
    units_sold: Decimal
    estimated_margin: Decimal | None  # (sales_price - cost_price) × units; None if unknown


@dataclass
class PlanPopularityRow:
    plan_id: int | None
    plan_name: str
    active_subscriptions: int
    mrr: Decimal


@dataclass
class ProductAnalytics:
    """Bundle returned by P2's analytics contract."""
    top_products_by_revenue: list[ProductRevenueRow] = field(default_factory=list)
    top_products_by_margin: list[ProductRevenueRow] = field(default_factory=list)
    most_popular_plans: list[PlanPopularityRow] = field(default_factory=list)
    underperforming_plans: list[PlanPopularityRow] = field(default_factory=list)
    available: bool = True
    note: str | None = None


class ProductAnalyticsProvider(Protocol):
    def product_analytics(self, session: Session) -> ProductAnalytics: ...


# --- P3: subscription intelligence --------------------------------------------

@dataclass
class RenewalRow:
    subscription_id: uuid.UUID
    subscription_number: str
    customer_id: uuid.UUID
    customer_name: str | None
    due_date: dt.date
    expected_amount: Decimal


@dataclass
class SubscriptionAnalytics:
    """Bundle returned by P3's analytics contract."""
    active_count: int = 0
    paused_count: int = 0
    closed_count: int = 0
    churned_last_30d: int = 0      # subscriptions closed within 30 days (proxy — no status history)
    renewals_due_30d: int = 0
    expiring_30d: int = 0
    upcoming_renewals: list[RenewalRow] = field(default_factory=list)
    available: bool = True
    note: str | None = None


class SubscriptionAnalyticsProvider(Protocol):
    def subscription_analytics(self, session: Session) -> SubscriptionAnalytics: ...
