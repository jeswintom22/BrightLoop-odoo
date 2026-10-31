"""In-memory stubs for the P1/P2/P3 contracts (integrations.py) so the billing
module runs end-to-end before the owning modules ship. Replace the factories in
app/deps.py with the real providers when they land.

Deterministic demo data: 3 customers, 5 subscriptions (3 due today monthly,
1 due weekly, 1 future, 1 expired).
"""

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from ...core.time import business_date
from .integrations import (
    CustomerView,
    PriceBreakdown,
    SubscriptionBillingView,
    SubscriptionLineView,
)

CENTS = Decimal("0.01")


def _uuid(seed: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-{seed:012d}")


class StubPricingProvider:
    """Flat unit prices + 18% GST — a stand-in for P2's real tax/discount engine."""

    def __init__(self, price_map: dict[uuid.UUID, Decimal] | None = None):
        self._prices = price_map or {}
        self._default = Decimal("999.00")

    def price_line(self, product_id, quantity, customer_id=None) -> PriceBreakdown:
        unit = self._prices.get(product_id, self._default)
        subtotal = (unit * quantity).quantize(CENTS)
        tax = (subtotal * Decimal("0.18")).quantize(CENTS)
        return PriceBreakdown(
            unit_price=unit,
            subtotal=subtotal,
            tax_total=tax,
            tax_details=[{"name": "GST", "rate": "18", "amount": str(tax)}],
            discount_total=Decimal("0.00"),
            discount_details=[],
            line_total=subtotal + tax,
        )


class StubCustomerProvider:
    def __init__(self):
        self._customers: dict[uuid.UUID, CustomerView] = {
            cid: CustomerView(
                id=cid,
                name=f"Demo Customer {i}",
                email=f"customer{i}@example.com",
                billing_address=f"{i} MG Road, Bengaluru",
            )
            for i, cid in enumerate([_uuid(101), _uuid(102), _uuid(103)], start=1)
        }

    def get(self, customer_id) -> CustomerView | None:
        return self._customers.get(customer_id)

    def get_many(self, ids) -> dict[uuid.UUID, CustomerView]:
        return {i: self._customers[i] for i in ids if i in self._customers}

    def ensure(self, customer_id: uuid.UUID) -> CustomerView:
        if customer_id not in self._customers:
            self._customers[customer_id] = CustomerView(
                id=customer_id,
                name=f"Customer {str(customer_id)[:8]}",
                email=f"{str(customer_id)[:8]}@example.com",
            )
        return self._customers[customer_id]


class StubSubscriptionProvider:
    def __init__(
        self,
        customers: StubCustomerProvider | None = None,
        views: list[SubscriptionBillingView] | None = None,
    ):
        self._customers = customers or StubCustomerProvider()
        if views is not None:
            self._subs = {v.id: v for v in views}
        else:
            self._subs = self._seed()

    def _seed(self) -> dict[uuid.UUID, SubscriptionBillingView]:
        today = business_date()
        customer_ids = list(self._customers._customers)
        subs: dict[uuid.UUID, SubscriptionBillingView] = {}

        def add(seed, customer_idx, freq, next_date, expiry=None):
            cid = customer_ids[customer_idx % len(customer_ids)]
            view = SubscriptionBillingView(
                id=_uuid(seed),
                customer_id=cid,
                status="active",
                billing_frequency=freq,
                next_billing_date=next_date,
                expiry_date=expiry,
                lines=[
                    SubscriptionLineView(
                        subscription_line_id=_uuid(seed + 500),
                        product_id=seed + 1000,
                        description=f"Pro plan ({freq})",
                        quantity=Decimal("1"),
                    )
                ],
            )
            subs[view.id] = view

        add(201, 0, "monthly", today)
        add(202, 1, "monthly", today - dt.timedelta(days=2))
        add(203, 2, "monthly", today)
        add(204, 0, "weekly", today)
        add(205, 1, "yearly", today + dt.timedelta(days=30))  # not due yet

        expired = SubscriptionBillingView(
            id=_uuid(206),
            customer_id=customer_ids[2],
            status="active",
            billing_frequency="monthly",
            next_billing_date=today - dt.timedelta(days=10),
            expiry_date=today - dt.timedelta(days=1),  # expired -> never due
            lines=[
                SubscriptionLineView(
                    subscription_line_id=_uuid(706),
                    product_id=1206,
                    description="Legacy plan",
                    quantity=Decimal("1"),
                )
            ],
        )
        subs[expired.id] = expired
        return subs

    def all(self) -> list[SubscriptionBillingView]:
        return list(self._subs.values())

    def get_subscription_view(self, subscription_id):
        return self._subs.get(subscription_id)

    def _is_due(self, v: SubscriptionBillingView, as_of: dt.date) -> bool:
        return (
            v.status == "active"
            and v.next_billing_date <= as_of
            and (v.expiry_date is None or v.expiry_date >= as_of)
        )

    def get_due_subscriptions(self, as_of, limit=200, offset=0):
        due = sorted(
            (v for v in self._subs.values() if self._is_due(v, as_of)),
            key=lambda v: v.next_billing_date,
        )
        return due[offset : offset + limit]

    def count_due(self, as_of) -> int:
        return sum(1 for v in self._subs.values() if self._is_due(v, as_of))

    def count_active(self) -> int:
        return sum(1 for v in self._subs.values() if v.status == "active")

    def advance_billing_date(self, session: Session, subscription_id, billed_period_end) -> None:
        view = self._subs[subscription_id]
        view.next_billing_date = billed_period_end

    def close_expired(self, session: Session, as_of) -> int:
        closed = 0
        for v in self._subs.values():
            if (
                v.status == "active"
                and v.expiry_date is not None
                and v.expiry_date < as_of
            ):
                v.status = "closed"
                closed += 1
        return closed
