from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Table, Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


# Association table for Discounts and Products (Many-to-Many)
discount_products = Table(
    "discount_products",
    Base.metadata,
    Column("discount_id", Integer, ForeignKey("discounts.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
)


class Discount(Base):
    __tablename__ = "discounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    discount_type: Mapped[str] = mapped_column(String(50), nullable=False)  # fixed_amount or percentage
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    min_purchase_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    applicable_products: Mapped[List["Product"]] = relationship(
        "Product", secondary=discount_products, back_populates="discounts"
    )
