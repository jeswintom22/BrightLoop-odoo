import enum
from datetime import datetime, date, timezone
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    Enum as SQLEnum,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LifecycleStatus(str, enum.Enum):
    DRAFT = "Draft"
    QUOTATION = "Quotation"
    CONFIRMED = "Confirmed"
    ACTIVE = "Active"
    PAUSED = "Paused"
    CLOSED = "Closed"


# Status aliases for domain-specific convenience
QuotationStatus = LifecycleStatus
SubscriptionStatus = LifecycleStatus


class BillingFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    quotation_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(
        SQLEnum(LifecycleStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=LifecycleStatus.DRAFT,
        nullable=False,
    )
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    template_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    lines: Mapped[List["QuotationLine"]] = relationship(
        "QuotationLine",
        back_populates="quotation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription",
        back_populates="quotation",
        uselist=False,
        lazy="selectin",
    )


class QuotationLine(Base):
    __tablename__ = "quotation_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    quotation_id: Mapped[int] = mapped_column(Integer, ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1.0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    tax_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    billing_frequency: Mapped[str] = mapped_column(String(50), default="monthly", nullable=False)

    # Relationship
    quotation: Mapped["Quotation"] = relationship("Quotation", back_populates="lines")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    subscription_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    quotation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("quotations.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LifecycleStatus] = mapped_column(
        SQLEnum(LifecycleStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=LifecycleStatus.ACTIVE,
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_billing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    billing_frequency: Mapped[str] = mapped_column(String(50), default="monthly", nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    pause_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    close_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    quotation: Mapped[Optional["Quotation"]] = relationship("Quotation", back_populates="subscription")
    lines: Mapped[List["SubscriptionLine"]] = relationship(
        "SubscriptionLine",
        back_populates="subscription",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SubscriptionLine(Base):
    __tablename__ = "subscription_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1.0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    tax_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    billing_frequency: Mapped[str] = mapped_column(String(50), default="monthly", nullable=False)

    # Relationship
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="lines")
