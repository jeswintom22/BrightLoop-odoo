"""Phase 1 completion: P1 auth/users/customers + P3 quotations/subscriptions.

Revision ID: 0002_phase1
Revises: 0001_billing
Create Date: 2026-10-31

Dialect-portable (sqlite dev/tests + Postgres prod): plain Column types, no
server-side enums/JSONB beyond the shared Base conventions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase1"
down_revision: Union[str, None] = "0001_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.Uuid


def upgrade() -> None:
    # ── P1: auth / users / customers / reset tokens ──────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "customers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50)),
        sa.Column("billing_address", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customers_email", "customers", ["email"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_prt_hash"),
    )
    op.create_index("ix_prt_user", "password_reset_tokens", ["user_id"])

    # ── P3: quotation templates ──────────────────────────────────────────────
    op.create_table(
        "quotation_templates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("validity_days", sa.Integer, nullable=False, server_default="15"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "quotation_template_lines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("template_id", UUID, sa.ForeignKey("quotation_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("subscription_plans.id", ondelete="SET NULL")),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_qtl_template", "quotation_template_lines", ["template_id"])

    # ── P3: quotations ───────────────────────────────────────────────────────
    op.create_table(
        "quotations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("quotation_number", sa.String(20), nullable=False),
        sa.Column("customer_id", UUID, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("template_id", UUID, sa.ForeignKey("quotation_templates.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.Date, nullable=False),
        sa.Column("valid_until", sa.Date, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("quotation_number", name="uq_quotation_number"),
    )
    op.create_index("ix_quotations_customer", "quotations", ["customer_id"])
    op.create_index("ix_quotations_status", "quotations", ["status"])

    op.create_table(
        "quotation_lines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("quotation_id", UUID, sa.ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("product_variant_id", sa.Integer, sa.ForeignKey("product_variants.id", ondelete="SET NULL")),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("subscription_plans.id", ondelete="SET NULL")),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_ql_quotation", "quotation_lines", ["quotation_id"])

    # ── P3: subscriptions (billing contract table) ───────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("subscription_number", sa.String(20), nullable=False),
        sa.Column("customer_id", UUID, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("subscription_plans.id", ondelete="SET NULL")),
        sa.Column("quotation_id", UUID, sa.ForeignKey("quotations.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("billing_frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("start_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("next_billing_date", sa.Date),
        sa.Column("payment_terms", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("subscription_number", name="uq_subscription_number"),
    )
    op.create_index("ix_subscriptions_customer", "subscriptions", ["customer_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index("ix_subscriptions_next_billing", "subscriptions", ["next_billing_date"])

    op.create_table(
        "subscription_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("subscription_id", UUID, sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("product_variant_id", sa.Integer, sa.ForeignKey("product_variants.id", ondelete="SET NULL")),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_si_subscription", "subscription_items", ["subscription_id"])

    # ── increments on existing tables ────────────────────────────────────────
    op.add_column(
        "billing_runs", sa.Column("closed", sa.Integer, nullable=False, server_default="0")
    )
    op.add_column(
        "discounts",
        sa.Column("min_quantity", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("discounts", "min_quantity")
    op.drop_column("billing_runs", "closed")
    op.drop_table("subscription_items")
    op.drop_table("subscriptions")
    op.drop_table("quotation_lines")
    op.drop_table("quotations")
    op.drop_table("quotation_template_lines")
    op.drop_table("quotation_templates")
    op.drop_table("password_reset_tokens")
    op.drop_table("customers")
    op.drop_table("users")
