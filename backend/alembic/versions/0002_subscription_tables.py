"""subscription tables (quotations, quotation_lines, subscriptions, subscription_lines)

Revision ID: 0002_subscriptions
Revises: 0001_billing
Create Date: 2026-10-31
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002_subscriptions"
down_revision: Union[str, None] = "0001_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. quotations table
    op.create_table(
        "quotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quotation_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("template_name", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotations_id", "quotations", ["id"], unique=False)
    op.create_index("ix_quotations_quotation_number", "quotations", ["quotation_number"], unique=True)
    op.create_index("ix_quotations_customer_id", "quotations", ["customer_id"], unique=False)

    # 2. quotation_lines table
    op.create_table(
        "quotation_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=100), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("tax_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("billing_frequency", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotation_lines_id", "quotation_lines", ["id"], unique=False)
    op.create_index("ix_quotation_lines_quotation_id", "quotation_lines", ["quotation_id"], unique=False)
    op.create_index("ix_quotation_lines_product_id", "quotation_lines", ["product_id"], unique=False)

    # 3. subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscription_number", sa.String(length=50), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_billing_date", sa.Date(), nullable=True),
        sa.Column("billing_frequency", sa.String(length=50), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("pause_reason", sa.Text(), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("paused_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"], unique=False)
    op.create_index("ix_subscriptions_subscription_number", "subscriptions", ["subscription_number"], unique=True)
    op.create_index("ix_subscriptions_customer_id", "subscriptions", ["customer_id"], unique=False)
    op.create_index("ix_subscriptions_quotation_id", "subscriptions", ["quotation_id"], unique=True)

    # 4. subscription_lines table
    op.create_table(
        "subscription_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=100), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("tax_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("billing_frequency", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscription_lines_id", "subscription_lines", ["id"], unique=False)
    op.create_index("ix_subscription_lines_subscription_id", "subscription_lines", ["subscription_id"], unique=False)
    op.create_index("ix_subscription_lines_product_id", "subscription_lines", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_table("subscription_lines")
    op.drop_table("subscriptions")
    op.drop_table("quotation_lines")
    op.drop_table("quotations")
