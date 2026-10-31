"""notification schedules, email templates, delivery retries, and admin settings

Revision ID: 0003_notification_ops
Revises: 0002_notifications
"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op


revision: str = "0003_notification_ops"
down_revision: Union[str, None] = "0002_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = sa.Uuid()
CATEGORIES = (
    "payment_due",
    "invoice_due",
    "payment_overdue",
    "subscription_renewal",
    "payment_confirmation",
    "invoice_generated",
)

DEFAULT_TEMPLATES = {
    "subscription_renewal": (
        "Subscription update: {{subscription_name}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1 style='font-size:22px'>Subscription update</h1><p>Hello {{customer_name}},</p><p><strong>{{subscription_name}}</strong> {{renewal_status}} on {{renewal_date}} for {{invoice_amount}}.</p><p>{{payment_instructions}}</p><p><a href='{{account_url}}'>View your account</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, {{subscription_name}} {{renewal_status}} on {{renewal_date}} for {{invoice_amount}}. {{payment_instructions}} {{account_url}}",
    ),
    "payment_confirmation": (
        "Payment received — {{transaction_id}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1 style='font-size:22px'>Payment confirmed</h1><p>Hello {{customer_name}},</p><p>We received {{invoice_amount}} on {{payment_date}}.</p><p>Transaction: {{transaction_id}} · Method: {{payment_method}}</p><p>Invoice {{invoice_number}}. Remaining balance: {{remaining_balance}}.</p><p><a href='{{invoice_url}}'>View invoice</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, payment {{transaction_id}} of {{invoice_amount}} was received on {{payment_date}} by {{payment_method}}. Invoice {{invoice_number}}. Remaining balance: {{remaining_balance}}. {{invoice_url}}",
    ),
    "invoice_generated": (
        "Invoice {{invoice_number}} is ready",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1 style='font-size:22px'>Your invoice is ready</h1><p>Hello {{customer_name}},</p><p>Invoice <strong>{{invoice_number}}</strong> dated {{invoice_date}} is {{payment_status}}.</p><p>Total: {{invoice_amount}} · Due: {{due_date}}</p><p>Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View or download invoice</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, invoice {{invoice_number}} dated {{invoice_date}} is {{payment_status}}. Total {{invoice_amount}}, due {{due_date}}, remaining {{remaining_balance}}. {{invoice_url}}",
    ),
    "invoice_due": (
        "Invoice {{invoice_number}} is due {{due_date}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1 style='font-size:22px'>Invoice payment reminder</h1><p>Hello {{customer_name}},</p><p>Invoice {{invoice_number}} is due on {{due_date}}.</p><p>Original total: {{invoice_amount}} · Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View invoice and payment options</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, invoice {{invoice_number}} is due {{due_date}}. Original total {{invoice_amount}}; remaining balance {{remaining_balance}}. {{invoice_url}}",
    ),
    "payment_overdue": (
        "Payment overdue: invoice {{invoice_number}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1 style='font-size:22px'>Overdue invoice notice</h1><p>Hello {{customer_name}},</p><p>Invoice {{invoice_number}} was due {{due_date}}.</p><p>Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View invoice and payment options</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, invoice {{invoice_number}} was due {{due_date}}. Remaining balance {{remaining_balance}}. {{invoice_url}}",
    ),
    "payment_due": (
        "Payment due: invoice {{invoice_number}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1 style='font-size:22px'>Payment due reminder</h1><p>Hello {{customer_name}},</p><p>Invoice {{invoice_number}} is due {{due_date}}.</p><p>Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View invoice</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, payment for invoice {{invoice_number}} is due {{due_date}}. Remaining balance {{remaining_balance}}. {{invoice_url}}",
    ),
}


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_constraint("ck_notifications_status", type_="check")
        batch.create_check_constraint(
            "ck_notifications_status",
            "status IN ('pending', 'sent', 'delivered', 'failed', 'read', 'cancelled')",
        )
        batch.add_column(sa.Column("idempotency_key", sa.String(255), nullable=True))
        batch.add_column(
            sa.Column("essential", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
    op.create_index(
        "ix_notifications_idempotency_key",
        "notifications",
        ["idempotency_key"],
        unique=True,
    )

    with op.batch_alter_table("notification_deliveries") as batch:
        batch.drop_constraint("ck_notification_deliveries_status", type_="check")
        batch.create_check_constraint(
            "ck_notification_deliveries_status",
            "delivery_status IN ('pending', 'sent', 'delivered', 'failed', 'cancelled')",
        )
        batch.add_column(
            sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("recipient_email", sa.String(320), nullable=True)
        )
        batch.add_column(sa.Column("subject", sa.String(255), nullable=True))
        batch.add_column(sa.Column("html_body", sa.Text(), nullable=True))
        batch.add_column(sa.Column("text_body", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("provider_event_id", sa.String(255), nullable=True)
        )
        batch.create_unique_constraint(
            "uq_notification_delivery_channel", ["notification_id", "channel"]
        )
    op.create_index(
        "uq_notification_delivery_provider_event",
        "notification_deliveries",
        ["provider_event_id"],
        unique=True,
    )

    op.create_table(
        "notification_reminder_rules",
        sa.Column("id", UUID, nullable=False),
        sa.Column("notification_type", sa.String(32), nullable=False),
        sa.Column("days_offset", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "notification_type IN ('invoice_due', 'payment_overdue', 'subscription_renewal')",
            name="ck_notification_reminder_rules_type",
        ),
        sa.CheckConstraint(
            "days_offset BETWEEN -365 AND 365 AND days_offset != 0",
            name="ck_notification_reminder_rules_offset",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_type", "days_offset",
            name="uq_notification_reminder_rules_type_offset",
        ),
    )

    op.create_table(
        "notification_templates",
        sa.Column("id", UUID, nullable=False),
        sa.Column("notification_type", sa.String(32), nullable=False),
        sa.Column("subject_template", sa.String(255), nullable=False),
        sa.Column("html_template", sa.Text(), nullable=False),
        sa.Column("text_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by", UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "notification_type IN ('payment_due', 'invoice_due', 'payment_overdue', "
            "'subscription_renewal', 'payment_confirmation', 'invoice_generated')",
            name="ck_notification_templates_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_type", name="uq_notification_templates_type"
        ),
    )

    op.create_table(
        "notification_category_settings",
        sa.Column("id", UUID, nullable=False),
        sa.Column("notification_type", sa.String(32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by", UUID, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "notification_type IN ('payment_due', 'invoice_due', 'payment_overdue', "
            "'subscription_renewal', 'payment_confirmation', 'invoice_generated')",
            name="ck_notification_category_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_type", name="uq_notification_category_type"
        ),
    )

    op.create_table(
        "notification_delivery_events",
        sa.Column("id", UUID, nullable=False),
        sa.Column("delivery_id", UUID, nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["notification_deliveries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id"),
    )
    op.create_index(
        "ix_notification_delivery_events_delivery_id",
        "notification_delivery_events",
        ["delivery_id"],
    )
    op.create_table(
        "notification_sender_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_name", sa.String(128), nullable=False),
        sa.Column("sender_email", sa.String(320), nullable=False),
        sa.Column("updated_by", UUID, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_notification_sender_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )

    rules = sa.table(
        "notification_reminder_rules",
        sa.column("id", UUID),
        sa.column("notification_type", sa.String),
        sa.column("days_offset", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        rules,
        [
            {"id": uuid.uuid4(), "notification_type": "subscription_renewal", "days_offset": n, "is_active": True}
            for n in (7, 3, 1)
        ]
        + [
            {"id": uuid.uuid4(), "notification_type": "invoice_due", "days_offset": n, "is_active": True}
            for n in (7, 3, 1)
        ]
        + [
            {"id": uuid.uuid4(), "notification_type": "payment_overdue", "days_offset": -n, "is_active": True}
            for n in (1, 7)
        ],
    )

    templates = sa.table(
        "notification_templates",
        sa.column("id", UUID),
        sa.column("notification_type", sa.String),
        sa.column("subject_template", sa.String),
        sa.column("html_template", sa.Text),
        sa.column("text_template", sa.Text),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        templates,
        [
            {
                "id": uuid.uuid4(),
                "notification_type": key,
                "subject_template": subject,
                "html_template": html,
                "text_template": text,
                "is_active": True,
            }
            for key, (subject, html, text) in DEFAULT_TEMPLATES.items()
        ],
    )

    categories = sa.table(
        "notification_category_settings",
        sa.column("id", UUID),
        sa.column("notification_type", sa.String),
        sa.column("is_enabled", sa.Boolean),
    )
    op.bulk_insert(
        categories,
        [
            {
                "id": uuid.uuid4(),
                "notification_type": category,
                "is_enabled": True,
            }
            for category in CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_table("notification_sender_settings")
    op.drop_index(
        "ix_notification_delivery_events_delivery_id",
        table_name="notification_delivery_events",
    )
    op.drop_table("notification_delivery_events")
    op.drop_table("notification_category_settings")
    op.drop_table("notification_templates")
    op.drop_table("notification_reminder_rules")
    op.drop_index(
        "uq_notification_delivery_provider_event",
        table_name="notification_deliveries",
    )
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.drop_constraint("uq_notification_delivery_channel", type_="unique")
        batch.drop_column("provider_event_id")
        batch.drop_column("text_body")
        batch.drop_column("html_body")
        batch.drop_column("subject")
        batch.drop_column("recipient_email")
        batch.drop_column("next_retry_at")
        batch.drop_column("attempt_count")
        batch.drop_constraint("ck_notification_deliveries_status", type_="check")
        batch.create_check_constraint(
            "ck_notification_deliveries_status",
            "delivery_status IN ('pending', 'sent', 'delivered', 'failed')",
        )
    op.drop_index("ix_notifications_idempotency_key", table_name="notifications")
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("essential")
        batch.drop_column("idempotency_key")
        batch.drop_constraint("ck_notifications_status", type_="check")
        batch.create_check_constraint(
            "ck_notifications_status",
            "status IN ('pending', 'sent', 'delivered', 'failed', 'read')",
        )
