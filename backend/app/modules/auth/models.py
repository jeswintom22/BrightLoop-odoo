"""P1 — auth domain: users, customers, password reset tokens.

`customers` is the billing-facing identity (uuid PK — matches
invoices.customer_id / subscriptions.customer_id); `users` is the login
identity linked 1:1 via customers.user_id.
"""

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base
from ...core.time import utc_now

ROLES = ("admin", "staff", "customer")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(sa.String(255))
    full_name: Mapped[str] = mapped_column(sa.String(255))
    role: Mapped[str] = mapped_column(sa.String(20), default="customer", index=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    customer: Mapped["Customer | None"] = relationship(
        "Customer", back_populates="user", uselist=False
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    name: Mapped[str] = mapped_column(sa.String(255))
    email: Mapped[str] = mapped_column(sa.String(255), index=True)
    phone: Mapped[str | None] = mapped_column(sa.String(50))
    billing_address: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now
    )

    user: Mapped[User | None] = relationship("User", back_populates="customer")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(sa.DateTime(timezone=True))
    used_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now
    )
