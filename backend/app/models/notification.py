import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('payment_due', 'invoice_due', 'payment_overdue', "
            "'subscription_renewal', 'payment_confirmation', 'invoice_generated')",
            name="ck_notifications_type",
        ),
        CheckConstraint(
            "channel IN ('in_app', 'email')", name="ck_notifications_channel"
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'delivered', 'failed', 'read', 'cancelled')",
            name="ck_notifications_status",
        ),
        Index("ix_notifications_customer_created", "customer_id", "created_at"),
        Index("ix_notifications_customer_read", "customer_id", "is_read"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="in_app")
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(64))
    related_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True
    )
    essential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )
