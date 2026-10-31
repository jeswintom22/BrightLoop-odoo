"""add customer notifications and notification preferences

Revision ID: 0002_notifications
Revises: 0003_finance_intelligence
Create Date: 2026-10-31

NOTE: revision id is historical — chain sits after 0003_finance_intelligence
to keep a single alembic head after merging into main.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_notifications"
down_revision: Union[str, None] = "0003_finance_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.Uuid


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), server_default="in_app", nullable=False),
        sa.Column("related_entity_type", sa.String(length=64), nullable=True),
        sa.Column("related_entity_id", UUID(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "notification_type IN ('payment_due', 'invoice_due', 'payment_overdue', "
            "'subscription_renewal', 'payment_confirmation', 'invoice_generated')",
            name="ck_notifications_type",
        ),
        sa.CheckConstraint(
            "channel IN ('in_app', 'email')", name="ck_notifications_channel"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'delivered', 'failed', 'read')",
            name="ck_notifications_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_customer_created",
        "notifications",
        ["customer_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_customer_read",
        "notifications",
        ["customer_id", "is_read"],
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("customer_id", UUID(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("payment_due_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("invoice_due_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("overdue_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("renewal_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "payment_confirmation_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "invoice_generated_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", name="uq_notification_preferences_customer"
        ),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("notification_id", UUID(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column(
            "delivery_status", sa.String(length=16), server_default="pending", nullable=False
        ),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "channel IN ('in_app', 'email')", name="ck_notification_deliveries_channel"
        ),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'delivered', 'failed')",
            name="ck_notification_deliveries_status",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_deliveries_notification_id",
        "notification_deliveries",
        ["notification_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_deliveries_notification_id",
        table_name="notification_deliveries",
    )
    op.drop_table("notification_deliveries")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_customer_read", table_name="notifications")
    op.drop_index("ix_notifications_customer_created", table_name="notifications")
    op.drop_table("notifications")
