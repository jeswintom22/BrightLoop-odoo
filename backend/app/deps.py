"""FastAPI dependencies: DB session, auth (P1 contract), internal token, providers."""

import uuid
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from .core.config import Settings, get_settings
from .core.database import SessionLocal, get_db
from .core.errors import AppError
from .modules.billing.integrations_stub import (
    StubCustomerProvider,
    StubPricingProvider,
    StubSubscriptionProvider,
)
from .modules.billing.service_billing import BillingService


# get_db is imported from app.core.database (shared with every module) and
# re-exported here so routers have a single deps import site.

# --- Auth (contract owned by Person 1) ---------------------------------------

@dataclass
class CurrentUser:
    id: uuid.UUID
    email: str
    roles: list[str] = field(default_factory=list)


DEV_USER = CurrentUser(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    email="finance@brightloop.dev",
    roles=["admin", "finance"],
)


def get_current_user(
    request: Request, settings: Settings = Depends(get_settings)
) -> CurrentUser:
    """Resolve the caller from a Bearer JWT issued by P1's auth module.
    [PROPOSED] claims shape: {sub: user_id, email, roles: [...]}."""
    if settings.AUTH_DEV_BYPASS:
        return DEV_USER
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AppError("UNAUTHENTICATED", "Missing bearer token", 401)
    try:
        claims = jwt.decode(
            auth[7:], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        raise AppError("UNAUTHENTICATED", "Invalid token", 401)
    return CurrentUser(
        id=uuid.UUID(str(claims["sub"])),
        email=str(claims.get("email", "")),
        roles=list(claims.get("roles", [])),
    )


def require_roles(*roles: str):
    """[PROPOSED] role names: admin / finance (write), viewer (read-only)."""

    def dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if roles and not set(roles) & set(user.roles):
            raise AppError("FORBIDDEN", "Insufficient role", 403)
        return user

    return dep


def verify_internal_token(
    x_internal_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    """Shared-secret auth for /internal/** (GitHub Actions only)."""
    if not x_internal_token or x_internal_token != settings.INTERNAL_JOB_TOKEN:
        raise AppError("FORBIDDEN", "Invalid internal token", 403)


# --- Module providers (P1/P2/P3 contracts — stubs until their modules land) ---

_pricing = StubPricingProvider()
_customers = StubCustomerProvider()
_subscriptions = StubSubscriptionProvider(_customers)


def get_pricing_provider() -> StubPricingProvider:
    return _pricing


def get_customer_provider() -> StubCustomerProvider:
    return _customers


def get_subscription_provider() -> StubSubscriptionProvider:
    return _subscriptions


def get_billing_service(
    pricing: StubPricingProvider = Depends(get_pricing_provider),
    subscriptions: StubSubscriptionProvider = Depends(get_subscription_provider),
    customers: StubCustomerProvider = Depends(get_customer_provider),
) -> BillingService:
    return BillingService(
        pricing=pricing, subscriptions=subscriptions, customers=customers
    )


def get_session_factory():
    return SessionLocal


DbDep = Depends(get_db)
