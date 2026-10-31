"""DB-backed providers — wired in app/deps.py when USE_STUB_PROVIDERS=false.

DbPricingProvider consumes P2's REAL catalog tables (products,
product_variants, subscription_plans, tax_configurations, discounts) — those
ship in this repo (app/models/*).

DbSubscriptionProvider / DbCustomerProvider implement the P3/P1 contracts
against the proposed contract schema (docs/architecture.md §7) via lightweight
Core table references — they deliberately do NOT register ORM models on
Base.metadata, so they cannot collide with the owners' real models when those
land. If P3/P1 ship different table or column names, adjust the *_TABLES /
*_COLS maps below — no other code needs to change.

KNOWN OPEN CONTRACT ITEM (needs team agreement): this module's views and the
invoices/invoice_lines FK columns assume UUID identifiers, while P2's catalog
uses Integer PKs. See docs/architecture.md §7 — until reconciled,
DbPricingProvider coerces int-shaped identifiers to int and passes others
through.
"""

import datetime as dt
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from ...core.time import utc_now
from .integrations import (
    CustomerView,
    PriceBreakdown,
    SubscriptionBillingView,
    SubscriptionLineView,
)

CENTS = Decimal("0.01")

# ---------------------------------------------------------------------------
# P1/P3 contract table maps — Core Table objects (NOT registered on
# Base.metadata). Adjust column names here if the owners ship different ones.
# ---------------------------------------------------------------------------

_CUSTOMERS_TABLE = sa.table(
    "customers",
    sa.column("id", sa.Uuid),
    sa.column("name"),
    sa.column("email"),
    sa.column("billing_address"),
)

_SUBSCRIPTIONS_TABLE = sa.table(
    "subscriptions",
    sa.column("id", sa.Uuid),
    sa.column("customer_id", sa.Uuid),
    sa.column("status"),
    sa.column("billing_frequency"),
    sa.column("next_billing_date", sa.Date),
    sa.column("expiry_date", sa.Date),
)

_SUBSCRIPTION_ITEMS_TABLE = sa.table(
    "subscription_items",
    sa.column("id", sa.Uuid),
    sa.column("subscription_id", sa.Uuid),
    sa.column("product_id", sa.Integer),
    sa.column("description"),
    sa.column("quantity"),
)


def _coerce_fk(value):
    """Cross-module ids: contract says UUID; owners may ship int PKs or UUID
    columns. Typed columns bind UUID objects correctly per-dialect — convert
    uuid-shaped strings, pass everything else through."""
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return value
    return value


class DbCustomerProvider:
    """P1 contract — reads customers directly from the shared database."""

    def __init__(self, session_factory: sessionmaker):
        self._sf = session_factory

    def _rows(self, ids: list) -> dict:
        if not ids:
            return {}
        with self._sf() as session:
            rows = session.execute(
                sa.select(_CUSTOMERS_TABLE).where(_CUSTOMERS_TABLE.c.id.in_(ids))
            ).mappings()
            return {r["id"]: r for r in rows}

    def get(self, customer_id) -> CustomerView | None:
        row = self._rows([_coerce_fk(customer_id)]).get(_coerce_fk(customer_id))
        if row is None:
            return None
        return CustomerView(
            id=customer_id,
            name=row["name"],
            email=row["email"],
            billing_address=row["billing_address"],
        )

    def get_many(self, ids) -> dict:
        rows = self._rows([_coerce_fk(i) for i in ids])
        return {
            i: CustomerView(
                id=i,
                name=row["name"],
                email=row["email"],
                billing_address=row["billing_address"],
            )
            for i in ids
            if (row := rows.get(_coerce_fk(i))) is not None
        }


class DbPricingProvider:
    """P2 contract — prices lines from the real catalog tables.

    unit price: products.sales_price (or subscription_plans.price when the
    subscription line maps to a plan — P3 lines carry product_id only today).
    tax:      products.tax_id -> tax_configurations.tax_percentage (is_active).
    discount: best single active discount linked via discount_products that is
    date-valid, under usage_limit, and whose min_purchase_amount <= subtotal.
    Percentage discounts apply to the subtotal; fixed_amount discounts are
    capped at the subtotal. Tax is charged on the discounted net.
    """

    def __init__(self, session_factory: sessionmaker):
        self._sf = session_factory

    def price_line(self, product_id, quantity, customer_id=None) -> PriceBreakdown:
        from app.models.discount import Discount
        from app.models.product import Product
        from app.models.tax import TaxConfiguration

        pid = _coerce_fk(product_id)
        quantity = Decimal(str(quantity))
        now = utc_now()

        with self._sf() as session:
            product = session.get(Product, pid) if isinstance(pid, int) else None
            if product is None or not product.is_active:
                unit = Decimal("0.00")
                tax_rate = Decimal("0")
                discounts: list = []
            else:
                unit = Decimal(str(product.sales_price))
                tax_rate = (
                    Decimal(str(product.tax.tax_percentage))
                    if product.tax_id and product.tax and product.tax.is_active
                    else Decimal("0")
                )
                discounts = (
                    session.execute(
                        sa.select(Discount)
                        .join(Discount.applicable_products)
                        .where(
                            Product.id == product.id,
                            Discount.is_active.is_(True),
                            Discount.start_date <= now,
                            sa.or_(
                                Discount.expiry_date.is_(None),
                                Discount.expiry_date >= now,
                            ),
                            sa.or_(
                                Discount.usage_limit.is_(None),
                                Discount.usage_count < Discount.usage_limit,
                            ),
                        )
                    )
                    .scalars()
                    .all()
                )

        subtotal = (unit * quantity).quantize(CENTS)

        discount_total = Decimal("0.00")
        discount_details: list[dict] = []
        for d in discounts:
            if Decimal(str(d.min_purchase_amount)) > subtotal:
                continue
            if Decimal(str(d.min_quantity or 0)) > quantity:
                continue
            amount = (
                (subtotal * Decimal(str(d.discount_value)) / Decimal("100"))
                if d.discount_type == "percentage"
                else Decimal(str(d.discount_value))
            )
            amount = min(amount.quantize(CENTS), subtotal)
            if amount > discount_total:
                discount_total = amount
                discount_details = [
                    {
                        "name": d.name,
                        "code": d.code,
                        "type": d.discount_type,
                        "value": str(d.discount_value),
                        "amount": str(amount),
                    }
                ]

        net = (subtotal - discount_total).quantize(CENTS)
        tax_total = (net * tax_rate / Decimal("100")).quantize(CENTS)
        tax_details = (
            [{"name": "Tax", "rate": str(tax_rate), "amount": str(tax_total)}]
            if tax_rate
            else []
        )

        return PriceBreakdown(
            unit_price=unit,
            subtotal=subtotal,
            tax_total=tax_total,
            tax_details=tax_details,
            discount_total=discount_total,
            discount_details=discount_details,
            line_total=(net + tax_total).quantize(CENTS),
        )


class DbSubscriptionProvider:
    """P3 contract — due-subscription queries + atomic date advancement."""

    def __init__(self, session_factory: sessionmaker):
        self._sf = session_factory

    def _view(self, row, items) -> SubscriptionBillingView:
        return SubscriptionBillingView(
            id=row["id"],
            customer_id=row["customer_id"],
            status=row["status"],
            billing_frequency=row["billing_frequency"],
            next_billing_date=row["next_billing_date"],
            expiry_date=row["expiry_date"],
            lines=[
                SubscriptionLineView(
                    subscription_line_id=i["id"],
                    product_id=i["product_id"],
                    description=i["description"] or "",
                    quantity=Decimal(str(i["quantity"])),
                )
                for i in items
            ],
        )

    def _items(self, session: Session, subscription_ids: list):
        if not subscription_ids:
            return {}
        rows = session.execute(
            sa.select(_SUBSCRIPTION_ITEMS_TABLE).where(
                _SUBSCRIPTION_ITEMS_TABLE.c.subscription_id.in_(subscription_ids)
            )
        ).mappings()
        items: dict = {}
        for r in rows:
            items.setdefault(r["subscription_id"], []).append(r)
        return items

    def get_subscription_view(self, subscription_id) -> SubscriptionBillingView | None:
        with self._sf() as session:
            row = session.execute(
                sa.select(_SUBSCRIPTIONS_TABLE).where(
                    _SUBSCRIPTIONS_TABLE.c.id == _coerce_fk(subscription_id)
                )
            ).mappings().first()
            if row is None:
                return None
            return self._view(row, self._items(session, [row["id"]]).get(row["id"], []))

    def get_due_subscriptions(self, as_of, limit=200, offset=0):
        with self._sf() as session:
            rows = session.execute(
                sa.select(_SUBSCRIPTIONS_TABLE)
                .where(
                    _SUBSCRIPTIONS_TABLE.c.status == "active",
                    _SUBSCRIPTIONS_TABLE.c.next_billing_date <= as_of,
                    sa.or_(
                        _SUBSCRIPTIONS_TABLE.c.expiry_date.is_(None),
                        _SUBSCRIPTIONS_TABLE.c.expiry_date >= as_of,
                    ),
                )
                .order_by(_SUBSCRIPTIONS_TABLE.c.next_billing_date)
                .limit(limit)
                .offset(offset)
            ).mappings().all()
            items = self._items(session, [r["id"] for r in rows])
            return [self._view(r, items.get(r["id"], [])) for r in rows]

    def count_due(self, as_of) -> int:
        with self._sf() as session:
            return session.scalar(
                sa.select(sa.func.count())
                .select_from(_SUBSCRIPTIONS_TABLE)
                .where(
                    _SUBSCRIPTIONS_TABLE.c.status == "active",
                    _SUBSCRIPTIONS_TABLE.c.next_billing_date <= as_of,
                    sa.or_(
                        _SUBSCRIPTIONS_TABLE.c.expiry_date.is_(None),
                        _SUBSCRIPTIONS_TABLE.c.expiry_date >= as_of,
                    ),
                )
            ) or 0

    def count_active(self) -> int:
        with self._sf() as session:
            return session.scalar(
                sa.select(sa.func.count())
                .select_from(_SUBSCRIPTIONS_TABLE)
                .where(_SUBSCRIPTIONS_TABLE.c.status == "active")
            ) or 0

    def advance_billing_date(
        self, session: Session, subscription_id, billed_period_end
    ) -> None:
        """UPDATE inside the caller's transaction — invoice + date move
        commit or roll back together (P3 contract requirement)."""
        session.execute(
            sa.update(_SUBSCRIPTIONS_TABLE)
            .where(_SUBSCRIPTIONS_TABLE.c.id == _coerce_fk(subscription_id))
            .values(next_billing_date=billed_period_end)
        )

    def close_expired(self, session: Session, as_of) -> int:
        from ..subscriptions.service_subscriptions import close_expired

        return close_expired(session, as_of)
