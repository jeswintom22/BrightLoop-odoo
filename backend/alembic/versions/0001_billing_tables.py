"""billing tables (invoices, invoice_lines, payments, billing_runs, number_counters)

Cross-module columns (subscription_id, customer_id, product_id, *_by) are plain
UUIDs without FK constraints until P1/P2/P3 ship their tables — see
docs/architecture.md §4/§7.

Dialect-portable: renders native UUID/JSONB/ENUM on Postgres, CHAR(32)/JSON/
VARCHAR+CHECK on SQLite (matching the models in app/modules/billing/models.py).

Revision ID: 0001_billing
Revises: 24b274a91357
Create Date: 2026-10-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_billing"
down_revision = "24b274a91357"  # P2 catalog tables migration runs first
branch_labels = None
depends_on = None

UUID = sa.Uuid
JSONB = sa.JSON().with_variant(postgresql.JSONB, "postgresql")

invoice_status = sa.Enum(
    "draft", "confirmed", "paid", "cancelled", name="invoice_status"
)
payment_method = sa.Enum(
    "upi", "bank_transfer", "cash", "card", "other", name="payment_method"
)
payment_status = sa.Enum("posted", "voided", name="payment_status")


def upgrade() -> None:
    op.create_table(
        "billing_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("trigger_source", sa.String(16), nullable=False),
        sa.Column("requested_by", UUID),
        sa.Column("run_for_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "invoices",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("invoice_number", sa.String(20), nullable=False, unique=True),
        sa.Column("subscription_id", UUID),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("status", invoice_status, nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("billing_run_id", UUID, sa.ForeignKey("billing_runs.id")),
        sa.Column("last_emailed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", UUID),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "subscription_id", "period_start", "period_end",
            name="uq_invoice_subscription_period",
        ),
        sa.CheckConstraint(
            "total_amount = subtotal + tax_total - discount_total",
            name="ck_invoice_total",
        ),
        sa.CheckConstraint("amount_paid >= 0", name="ck_invoice_amount_paid"),
    )
    op.create_index("ix_invoices_status_due", "invoices", ["status", "due_date"])
    op.create_index("ix_invoices_customer", "invoices", ["customer_id"])
    op.create_index("ix_invoices_issue_date", "invoices", ["issue_date"])
    op.create_index("ix_invoices_subscription_id", "invoices", ["subscription_id"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("invoice_id", UUID,
                  sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer),
        sa.Column("subscription_line_id", UUID),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("meta", JSONB),
    )
    op.create_index("ix_invoice_lines_invoice", "invoice_lines", ["invoice_id"])

    op.create_table(
        "payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("payment_reference", sa.String(20), nullable=False, unique=True),
        sa.Column("invoice_id", UUID, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("method", payment_method, nullable=False),
        sa.Column("status", payment_status, nullable=False, server_default="posted"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(64), unique=True),
        sa.Column("notes", sa.Text()),
        sa.Column("recorded_by", UUID),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount"),
    )
    op.create_index("ix_payments_invoice", "payments", ["invoice_id"])
    op.create_index("ix_payments_paid_at", "payments", ["paid_at"])
    op.create_index("ix_payments_status", "payments", ["status"])

    op.create_table(
        "number_counters",
        sa.Column("name", sa.String(32), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("next_value", sa.BigInteger(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("number_counters")
    op.drop_table("payments")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("billing_runs")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        payment_status.drop(bind, checkfirst=True)
        payment_method.drop(bind, checkfirst=True)
        invoice_status.drop(bind, checkfirst=True)
