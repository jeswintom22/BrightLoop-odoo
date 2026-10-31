import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Numeric, Boolean, Date, DateTime, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.product_variant import ProductVariant
    from app.models.tax import TaxConfiguration


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_variant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tax_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("tax_configurations.id"), nullable=True, index=True
    )

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    billing_frequency: Mapped[str] = mapped_column(
        String(50), nullable=False, default="monthly"
    )  # daily, weekly, monthly, yearly
    minimum_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    available_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )  # active, inactive, archived

    # Plan Lifecycle Settings
    allow_pause: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_renewal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_early_closure: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    automatic_closure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="subscription_plans")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant", back_populates="subscription_plans")
    tax: Mapped[Optional["TaxConfiguration"]] = relationship("TaxConfiguration", back_populates="subscription_plans")
