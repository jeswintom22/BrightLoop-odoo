import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, Text, Numeric, Boolean, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product_variant import ProductVariant
    from app.models.subscription_plan import SubscriptionPlan
    from app.models.tax import TaxConfiguration
    from app.models.discount import Discount


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(50), nullable=False, default="service")
    sales_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tax_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("tax_configurations.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tax: Mapped[Optional["TaxConfiguration"]] = relationship("TaxConfiguration", back_populates="products")
    variants: Mapped[List["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )
    subscription_plans: Mapped[List["SubscriptionPlan"]] = relationship(
        "SubscriptionPlan", back_populates="product", cascade="all, delete-orphan"
    )
    discounts: Mapped[List["Discount"]] = relationship(
        "Discount", secondary="discount_products", back_populates="applicable_products"
    )
