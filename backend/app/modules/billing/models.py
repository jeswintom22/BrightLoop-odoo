"""Billing module tables — see docs/architecture.md §4.

Cross-module columns (subscription_id, customer_id, product_id, created_by,
recorded_by, requested_by, subscription_line_id) intentionally carry NO
database-level FK yet: the referenced tables are owned by P1/P2/P3 and do not
exist in this migration tree. Add real ForeignKey constraints in a later
migration once the owning modules ship — see architecture doc §7.
"""

import datetime as dt
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base
from ...core.time import utc_now

JSONB = sa.JSON().with_variant(postgresql.JSONB, "postgresql")

invoice_status_enum = sa.Enum(
    "draft", "confirmed", "paid", "cancelled", name="invoice_status"
)
payment_method_enum = sa.Enum(
    "upi", "bank_transfer", "cash", "card", "other", name="payment_method"
)
payment_status_enum = sa.Enum("posted", "voided", name="payment_status")


class BillingRun(Base):
    __tablename__ = "billing_runs"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    trigger_source: Mapped[str] = mapped_column(sa.String(16))  # scheduled | manual
    requested_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)  # P1 users.id
    run_for_date: Mapped[dt.date] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(sa.String(16), default="running")
    scanned: Mapped[int] = mapped_column(sa.Integer, default=0)
    generated: Mapped[int] = mapped_column(sa.Integer, default=0)
    skipped: Mapped[int] = mapped_column(sa.Integer, default=0)
    failed: Mapped[int] = mapped_column(sa.Integer, default=0)
    closed: Mapped[int] = mapped_column(sa.Integer, default=0)
    errors: Mapped[list | None] = mapped_column(JSONB)
    started_at: Mapped[dt.datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="billing_run")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # The anti-duplicate guarantee for recurring billing.
        sa.UniqueConstraint(
            "subscription_id",
            "period_start",
            "period_end",
            name="uq_invoice_subscription_period",
        ),
        sa.CheckConstraint(
            "total_amount = subtotal + tax_total - discount_total",
            name="ck_invoice_total",
        ),
        sa.CheckConstraint("amount_paid >= 0", name="ck_invoice_amount_paid"),
        sa.Index("ix_invoices_status_due", "status", "due_date"),
        sa.Index("ix_invoices_customer", "customer_id"),
        sa.Index("ix_invoices_issue_date", "issue_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(sa.String(20), unique=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, index=True)  # P3
    customer_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid)  # P1
    status: Mapped[str] = mapped_column(invoice_status_enum, default="draft")
    issue_date: Mapped[dt.date] = mapped_column(sa.Date)
    due_date: Mapped[dt.date] = mapped_column(sa.Date)
    period_start: Mapped[dt.date] = mapped_column(sa.Date)
    period_end: Mapped[dt.date] = mapped_column(sa.Date)
    currency: Mapped[str] = mapped_column(sa.String(3), default="INR")
    subtotal: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2))
    tax_total: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2))
    # Maintained transactionally by payment writes — outstanding needs no join.
    amount_paid: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(sa.Text)
    billing_run_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("billing_runs.id")
    )
    last_emailed_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)  # P1 users.id
    created_at: Mapped[dt.datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.position",
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")
    billing_run: Mapped[BillingRun | None] = relationship(back_populates="invoices")

    @property
    def outstanding(self) -> Decimal:
        return (self.total_amount or Decimal("0")) - (self.amount_paid or Decimal("0"))


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (sa.Index("ix_invoice_lines_invoice", "invoice_id"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("invoices.id", ondelete="CASCADE")
    )
    product_id: Mapped[int | None] = mapped_column(sa.Integer)  # P2 products.id
    subscription_line_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)  # P3
    description: Mapped[str] = mapped_column(sa.String(255))
    position: Mapped[int] = mapped_column(sa.Integer, default=0)
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2))
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2))  # snapshot
    subtotal: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2))
    tax_amount: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2))
    # {tax_name, tax_rate, discount_name, ...} — breakdown snapshot.
    meta: Mapped[dict | None] = mapped_column(JSONB)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        sa.CheckConstraint("amount > 0", name="ck_payment_amount"),
        sa.Index("ix_payments_invoice", "invoice_id"),
        sa.Index("ix_payments_paid_at", "paid_at"),
        sa.Index("ix_payments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    payment_reference: Mapped[str] = mapped_column(sa.String(20), unique=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("invoices.id"))
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2))
    method: Mapped[str] = mapped_column(payment_method_enum)
    status: Mapped[str] = mapped_column(payment_status_enum, default="posted")
    paid_at: Mapped[dt.datetime] = mapped_column(sa.DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(sa.String(64), unique=True)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid)  # P1 users.id
    voided_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(sa.String(255))
    created_at: Mapped[dt.datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class NumberCounter(Base):
    """Row-locked counters for invoice/payment numbers (numbering.py)."""

    __tablename__ = "number_counters"

    name: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    year: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    next_value: Mapped[int] = mapped_column(sa.BigInteger, default=1)
