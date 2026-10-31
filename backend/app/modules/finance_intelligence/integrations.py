"""DB-backed implementations of the P2/P3 analytics contracts.

INTERIM IMPLEMENTATIONS — these compute the contract DTOs from the shared
database tables until Person 2 and Person 3 ship their own analytics
services. They read REAL records (no mock data); when the owners provide
native services, swap the factories in ``app/deps.py`` and the copilot is
unchanged.

Known data limitations (documented, never hidden from callers):
- ``estimated_margin`` uses product.cost_price when set; otherwise None —
  we do not fabricate profitability.
- churned_last_30d approximates churn from subscriptions.updated_at within
  30 days whose status is now 'closed' — the schema has no status-change
  history, so the closure date is approximate.
"""

import datetime as dt
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ...core.time import business_date
from ...models.product import Product
from ...models.subscription_plan import SubscriptionPlan
from ..auth.models import Customer
from ..billing.models import Invoice, InvoiceLine
from ..subscriptions.models import Subscription
from .analytics.mrr_arr import monthly_factor
from .contracts import (
    PlanPopularityRow,
    ProductAnalytics,
    ProductRevenueRow,
    RenewalRow,
    SubscriptionAnalytics,
)

CENTS = Decimal("0.01")


class DbProductAnalyticsProvider:
    """P2 contract — product revenue, margin and plan popularity."""

    def product_analytics(self, session: Session) -> ProductAnalytics:
        today = business_date()

        revenue_rows = session.execute(
            sa.select(
                InvoiceLine.product_id,
                sa.func.coalesce(Product.name, InvoiceLine.description).label("name"),
                sa.func.sum(InvoiceLine.line_total).label("revenue"),
                sa.func.sum(InvoiceLine.quantity).label("units"),
            )
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
            .outerjoin(Product, InvoiceLine.product_id == Product.id)
            .where(Invoice.status.in_(["confirmed", "paid"]))
            .group_by(InvoiceLine.product_id, "name")
            .order_by(sa.desc("revenue"))
        ).all()

        def to_row(pid, name, revenue_, units) -> ProductRevenueRow:
            revenue_ = Decimal(str(revenue_ or 0))
            units_ = Decimal(str(units or 0))
            margin = None
            if pid is not None:
                product = session.get(Product, pid)
                if product is not None:
                    unit_margin = Decimal(str(product.sales_price or 0)) - Decimal(
                        str(product.cost_price or 0)
                    )
                    margin = (unit_margin * units_).quantize(CENTS)
            return ProductRevenueRow(
                product_id=pid,
                product_name=str(name),
                invoiced_revenue=revenue_.quantize(CENTS),
                units_sold=units_,
                estimated_margin=margin,
            )

        rows = [to_row(pid, name, rev, units) for pid, name, rev, units in revenue_rows]
        by_margin = sorted(
            (r for r in rows if r.estimated_margin is not None),
            key=lambda r: r.estimated_margin,
            reverse=True,
        )

        plan_rows = session.execute(
            sa.select(
                Subscription.plan_id,
                sa.func.coalesce(SubscriptionPlan.name, sa.literal("No plan")).label("name"),
                sa.func.count(Subscription.id).label("subs"),
            )
            .outerjoin(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
            .where(Subscription.status == "active")
            .group_by(Subscription.plan_id, "name")
            .order_by(sa.desc("subs"))
        ).all()

        # MRR per plan for popularity ranking
        mrr_per_sub = {}
        for sub in session.scalars(
            sa.select(Subscription).where(Subscription.status == "active")
        ).all():
            cycle = sum(
                (
                    Decimal(str(i.quantity or 0)) * Decimal(str(i.unit_price or 0))
                    for i in sub.items
                ),
                Decimal("0"),
            )
            mrr_per_sub[sub.id] = cycle * monthly_factor(sub.billing_frequency)

        sub_plan = dict(
            session.execute(
                sa.select(Subscription.id, Subscription.plan_id).where(
                    Subscription.status == "active"
                )
            ).all()
        )
        plan_mrr: dict[uuid.UUID | None, Decimal] = {}
        for sub_id, plan_id in sub_plan.items():
            plan_mrr[plan_id] = plan_mrr.get(plan_id, Decimal("0")) + mrr_per_sub.get(
                sub_id, Decimal("0")
            )

        plans = [
            PlanPopularityRow(
                plan_id=pid,
                plan_name=str(name),
                active_subscriptions=int(count),
                mrr=plan_mrr.get(pid, Decimal("0")).quantize(CENTS),
            )
            for pid, name, count in plan_rows
        ]
        popular = sorted(plans, key=lambda r: (r.active_subscriptions, r.mrr), reverse=True)
        underperforming = sorted(plans, key=lambda r: r.mrr)[:5]

        return ProductAnalytics(
            top_products_by_revenue=rows[:10],
            top_products_by_margin=by_margin[:10],
            most_popular_plans=popular[:10],
            underperforming_plans=underperforming,
            available=True,
            note=None,
        )


class DbSubscriptionAnalyticsProvider:
    """P3 contract — churn/retention/renewal indicators."""

    def subscription_analytics(self, session: Session) -> SubscriptionAnalytics:
        today = business_date()
        in_30 = today + dt.timedelta(days=30)
        ago_30 = today - dt.timedelta(days=30)

        counts = dict(
            session.execute(
                sa.select(Subscription.status, sa.func.count(Subscription.id)).group_by(
                    Subscription.status
                )
            ).all()
        )

        churned = session.scalar(
            sa.select(sa.func.count(Subscription.id)).where(
                Subscription.status == "closed",
                Subscription.updated_at
                >= dt.datetime.combine(ago_30, dt.time.min, tzinfo=dt.timezone.utc),
            )
        ) or 0

        renewals_due = session.scalar(
            sa.select(sa.func.count(Subscription.id)).where(
                Subscription.status == "active",
                Subscription.next_billing_date.is_not(None),
                Subscription.next_billing_date >= today,
                Subscription.next_billing_date <= in_30,
            )
        ) or 0

        expiring = session.scalar(
            sa.select(sa.func.count(Subscription.id)).where(
                Subscription.status == "active",
                Subscription.expiry_date.is_not(None),
                Subscription.expiry_date >= today,
                Subscription.expiry_date <= in_30,
            )
        ) or 0

        renewal_rows = session.execute(
            sa.select(Subscription, Customer.name)
            .outerjoin(Customer, Subscription.customer_id == Customer.id)
            .where(
                Subscription.status == "active",
                Subscription.next_billing_date.is_not(None),
                Subscription.next_billing_date >= today,
                Subscription.next_billing_date <= in_30,
            )
            .order_by(Subscription.next_billing_date)
            .limit(20)
        ).all()

        renewals = []
        for sub, cust_name in renewal_rows:
            amount = Decimal("0")
            for item in sub.items:
                qty = Decimal(str(item.quantity or 0))
                unit = Decimal(str(item.unit_price or 0))
                tax = Decimal(str(item.tax_rate or 0))
                amount += qty * unit * (1 + tax / Decimal("100"))
            renewals.append(
                RenewalRow(
                    subscription_id=sub.id,
                    subscription_number=sub.subscription_number,
                    customer_id=sub.customer_id,
                    customer_name=cust_name,
                    due_date=sub.next_billing_date,
                    expected_amount=amount.quantize(CENTS),
                )
            )

        return SubscriptionAnalytics(
            active_count=int(counts.get("active", 0)),
            paused_count=int(counts.get("paused", 0)),
            closed_count=int(counts.get("closed", 0)),
            churned_last_30d=int(churned),
            renewals_due_30d=int(renewals_due),
            expiring_30d=int(expiring),
            upcoming_renewals=renewals,
            available=True,
            note=(
                "churned_last_30d approximates closure time from updated_at — "
                "no status-change history exists in the schema."
            ),
        )
