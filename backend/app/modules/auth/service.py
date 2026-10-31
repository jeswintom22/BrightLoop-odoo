"""P1 auth service — registration, login, password reset, staff/customer mgmt."""

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import AppError
from ...core.time import utc_now
from .models import Customer, PasswordResetToken, User
from .security import (
    hash_password,
    hash_token,
    issue_token,
    new_reset_token,
    verify_password,
)

RESET_TTL_MINUTES = 30


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def register_customer(
    session: Session, *, email: str, password: str, full_name: str,
    phone: str | None = None, billing_address: str | None = None,
) -> tuple[User, str]:
    email = _normalize_email(email)
    if session.scalar(sa.select(User).where(User.email == email)):
        raise AppError("EMAIL_TAKEN", "Email already registered", 409)
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        role="customer",
    )
    session.add(user)
    session.flush()
    customer = Customer(
        user_id=user.id, name=user.full_name, email=email,
        phone=phone, billing_address=billing_address,
    )
    session.add(customer)
    session.flush()
    return user, issue_token(user)


def login(session: Session, *, email: str, password: str) -> tuple[User, str]:
    user = session.scalar(
        sa.select(User).where(User.email == _normalize_email(email))
    )
    # identical failure for unknown email vs bad password (no enumeration)
    if user is None or not verify_password(password, user.hashed_password):
        raise AppError("UNAUTHENTICATED", "Invalid email or password", 401)
    if not user.is_active:
        raise AppError("FORBIDDEN", "Account is disabled", 403)
    return user, issue_token(user)


def request_password_reset(session: Session, *, email: str) -> str | None:
    """Creates a reset token if the email exists; ALWAYS returns the raw token
    or None — callers MUST respond identically either way (no enumeration).
    The raw token is returned so the email layer can embed it."""
    user = session.scalar(
        sa.select(User).where(User.email == _normalize_email(email))
    )
    if user is None or not user.is_active:
        return None
    raw, digest = new_reset_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=digest,
            expires_at=utc_now() + dt.timedelta(minutes=RESET_TTL_MINUTES),
        )
    )
    session.flush()
    return raw


def reset_password(session: Session, *, token: str, new_password: str) -> User:
    row = session.scalar(
        sa.select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token)
        )
    )
    now = utc_now()
    if (
        row is None
        or row.used_at is not None
        or row.expires_at.replace(tzinfo=row.expires_at.tzinfo or dt.timezone.utc) < now
    ):
        raise AppError(
            "INVALID_TOKEN", "Reset link is invalid or has expired", 400
        )
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise AppError("INVALID_TOKEN", "Reset link is invalid or has expired", 400)
    user.hashed_password = hash_password(new_password)
    row.used_at = now  # single-use
    session.flush()
    return user


def create_staff(
    session: Session, *, email: str, password: str, full_name: str, role: str
) -> User:
    if role not in ("admin", "staff"):
        raise AppError("VALIDATION", "role must be admin or staff", 400)
    email = _normalize_email(email)
    if session.scalar(sa.select(User).where(User.email == email)):
        raise AppError("EMAIL_TAKEN", "Email already registered", 409)
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        role=role,
    )
    session.add(user)
    session.flush()
    return user


def get_customer_for_user(session: Session, user_id: uuid.UUID) -> Customer | None:
    return session.scalar(sa.select(Customer).where(Customer.user_id == user_id))


def seed_dev_admin(session: Session) -> None:
    """Dev convenience (AUTH_DEV_BYPASS path): ensures an admin login exists."""
    if session.scalar(sa.select(User).where(User.role == "admin")):
        return
    admin = User(
        email="admin@brightloop.dev",
        hashed_password=hash_password("Admin@12345"),
        full_name="Dev Admin",
        role="admin",
    )
    session.add(admin)
    session.flush()
