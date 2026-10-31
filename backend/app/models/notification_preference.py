import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_notification_preferences_customer"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payment_due_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    invoice_due_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    overdue_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    renewal_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payment_confirmation_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    invoice_generated_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
