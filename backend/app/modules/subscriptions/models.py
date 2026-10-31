"""P3 — quotations & subscription lifecycle.

Table/column names for `subscriptions`/`subscription_items` intentionally
match the billing contract consumed by
modules/billing/integrations_db.py::DbSubscriptionProvider — when these
tables exist, USE_STUB_PROVIDERS=false switches billing onto real data
with zero code changes there.

UUID PKs align with billing's FK columns (invoices.subscription_id,
invoice_lines.subscription_line_id are uuid-typed).
"""

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base
from ...core.time import utc_now

SUBSCRIPTION_STATUSES = ("draft", "confirmed", "active", "paused", "closed")
QUOTATION_STATUSES = ("draft", "sent", "confirmed", "expired", "cancelled", "converted")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)


class QuotationTemplate(Base):
    __tablename__ = "quotation_templates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(sa.String(255))
    description: Mapped[str | None] = mapped_column(sa.Text)
    validity_days: Mapped[int] = mapped_column(sa.Integer, default=15)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now
    )

    lines: Mapped[list["QuotationTemplateLine"]] = relationship(
        "QuotationTemplateLine", back_populates="template",
        cascade="all, delete-orphan", order_by="QuotationTemplateLine.position",
    )


class QuotationTemplateLine(Base):
    __tablename__ = "quotation_template_lines"

    id: Mapped[uuid.UUID] = _uuid_pk()
    template_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("quotation_templates.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL")
    )
    plan_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("subscription_plans.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(sa.String(255), default="")
    quantity: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=1)
    position: Mapped[int] = mapped_column(sa.Integer, default=0)

    template: Mapped[QuotationTemplate] = relationship(back_populates="lines")


class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    quotation_number: Mapped[str] = mapped_column(sa.String(20), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("customers.id"), index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("quotation_templates.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(sa.String(20), default="draft", index=True)
    issue_date: Mapped[dt.date] = mapped_column(sa.Date)
    valid_until: Mapped[dt.date] = mapped_column(sa.Date)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    subtotal: Mapped[float] = mapped_column(sa.Numeric(14, 2), default=0)
    tax_total: Mapped[float] = mapped_column(sa.Numeric(14, 2), default=0)
    discount_total: Mapped[float] = mapped_column(sa.Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(sa.Numeric(14, 2), default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now
    )

    lines: Mapped[list["QuotationLine"]] = relationship(
        "QuotationLine", back_populates="quotation",
        cascade="all, delete-orphan", order_by="QuotationLine.position",
    )


class QuotationLine(Base):
    __tablename__ = "quotation_lines"

    id: Mapped[uuid.UUID] = _uuid_pk()
    quotation_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("quotations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL")
    )
    product_variant_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    plan_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("subscription_plans.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(sa.String(255), default="")
    quantity: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=1)
    unit_price: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(sa.Numeric(5, 2), default=0)
    line_total: Mapped[float] = mapped_column(sa.Numeric(14, 2), default=0)
    position: Mapped[int] = mapped_column(sa.Integer, default=0)

    quotation: Mapped[Quotation] = relationship(back_populates="lines")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    subscription_number: Mapped[str] = mapped_column(sa.String(20), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("customers.id"), index=True
    )
    plan_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("subscription_plans.id", ondelete="SET NULL")
    )
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("quotations.id", ondelete="SET NULL")
    )
    # draft -> confirmed -> active <-> paused -> closed
    status: Mapped[str] = mapped_column(sa.String(20), default="draft", index=True)
    billing_frequency: Mapped[str] = mapped_column(sa.String(20), default="monthly")
    start_date: Mapped[dt.date | None] = mapped_column(sa.Date)
    expiry_date: Mapped[dt.date | None] = mapped_column(sa.Date)
    next_billing_date: Mapped[dt.date | None] = mapped_column(sa.Date, index=True)
    payment_terms: Mapped[str | None] = mapped_column(sa.String(100))
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    items: Mapped[list["SubscriptionItem"]] = relationship(
        "SubscriptionItem", back_populates="subscription",
        cascade="all, delete-orphan", order_by="SubscriptionItem.position",
    )


class SubscriptionItem(Base):
    __tablename__ = "subscription_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL")
    )
    product_variant_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(sa.String(255), default="")
    quantity: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=1)
    unit_price: Mapped[float] = mapped_column(sa.Numeric(12, 2), default=0)
    tax_rate: Mapped[float] = mapped_column(sa.Numeric(5, 2), default=0)
    position: Mapped[int] = mapped_column(sa.Integer, default=0)

    subscription: Mapped[Subscription] = relationship(back_populates="items")
