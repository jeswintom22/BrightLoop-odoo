import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationReminderRule(Base):
    __tablename__ = "notification_reminder_rules"
    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('invoice_due', 'payment_overdue', 'subscription_renewal')",
            name="ck_notification_reminder_rules_type",
        ),
        CheckConstraint(
            "days_offset BETWEEN -365 AND 365 AND days_offset != 0",
            name="ck_notification_reminder_rules_offset",
        ),
        UniqueConstraint(
            "notification_type",
            "days_offset",
            name="uq_notification_reminder_rules_type_offset",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    days_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint("notification_type", name="uq_notification_templates_type"),
        CheckConstraint(
            "notification_type IN ('payment_due', 'invoice_due', 'payment_overdue', "
            "'subscription_renewal', 'payment_confirmation', 'invoice_generated')",
            name="ck_notification_templates_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_template: Mapped[str] = mapped_column(String(255), nullable=False)
    html_template: Mapped[str] = mapped_column(Text, nullable=False)
    text_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class NotificationCategorySetting(Base):
    __tablename__ = "notification_category_settings"
    __table_args__ = (
        UniqueConstraint("notification_type", name="uq_notification_category_type"),
        CheckConstraint(
            "notification_type IN ('payment_due', 'invoice_due', 'payment_overdue', "
            "'subscription_renewal', 'payment_confirmation', 'invoice_generated')",
            name="ck_notification_category_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class NotificationDeliveryEvent(Base):
    __tablename__ = "notification_delivery_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    delivery_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("notification_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_event_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class NotificationSenderSetting(Base):
    __tablename__ = "notification_sender_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_notification_sender_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sender_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
