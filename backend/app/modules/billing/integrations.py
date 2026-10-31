"""Contracts this module consumes from P1/P2/P3 — ALL [PROPOSED], see
docs/architecture.md §7. Consumed in-process (same SQLAlchemy session for
writes), not over HTTP. Until the owning modules ship, integrations_stub.py
provides in-memory implementations wired in app/deps.py.
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session


# --- P1: customers ------------------------------------------------------------

@dataclass
class CustomerView:
    id: uuid.UUID
    name: str
    email: str
    billing_address: str | None = None


class CustomerProvider(Protocol):
    def get(self, customer_id: uuid.UUID) -> CustomerView | None: ...
    def get_many(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, CustomerView]: ...


# --- P2: catalog / pricing -----------------------------------------------------

@dataclass
class PriceBreakdown:
    unit_price: Decimal
    subtotal: Decimal
    tax_total: Decimal
    tax_details: list[dict] = field(default_factory=list)
    discount_total: Decimal = Decimal("0")
    discount_details: list[dict] = field(default_factory=list)
    line_total: Decimal = Decimal("0")


class PricingProvider(Protocol):
    def price_line(
        self,
        product_id: uuid.UUID | None,
        quantity: Decimal,
        customer_id: uuid.UUID | None = None,
    ) -> PriceBreakdown: ...


# --- P3: subscriptions ----------------------------------------------------------

@dataclass
class SubscriptionLineView:
    subscription_line_id: uuid.UUID
    product_id: uuid.UUID | None
    description: str
    quantity: Decimal


@dataclass
class SubscriptionBillingView:
    id: uuid.UUID
    customer_id: uuid.UUID
    status: str  # P3 owns allowed values; billing only bills "active"
    billing_frequency: str  # daily | weekly | monthly | yearly
    next_billing_date: dt.date
    expiry_date: dt.date | None = None
    lines: list[SubscriptionLineView] = field(default_factory=list)


class SubscriptionProvider(Protocol):
    def get_subscription_view(
        self, subscription_id: uuid.UUID
    ) -> SubscriptionBillingView | None: ...

    def get_due_subscriptions(
        self, as_of: dt.date, limit: int = 200, offset: int = 0
    ) -> list[SubscriptionBillingView]: ...

    def count_due(self, as_of: dt.date) -> int: ...
    def count_active(self) -> int: ...

    def advance_billing_date(
        self,
        session: Session,
        subscription_id: uuid.UUID,
        billed_period_end: dt.date,
    ) -> None:
        """Move next_billing_date past billed_period_end. MUST participate in the
        caller's transaction so invoice + date advancement commit atomically."""
        ...

    def close_expired(self, session: Session, as_of: dt.date) -> int:
        """Auto-close active subscriptions past expiry when the plan configures
        auto_closure. Runs inside the caller's session before the due-scan so
        manual and scheduled billing apply identical lifecycle rules."""
        ...
