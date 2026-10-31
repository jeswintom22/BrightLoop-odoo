"""FastAPI dependencies: DB session, auth (P1 contract), internal token, providers."""

import uuid
from dataclasses import dataclass, field

import jwt
import sqlalchemy as sa
from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from .core.config import Settings, get_settings
from .core.database import SessionLocal, get_db
from .core.errors import AppError
from .modules.billing.integrations_db import (
    DbCustomerProvider,
    DbPricingProvider,
    DbSubscriptionProvider,
)
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
    email="admin@brightloop.dev",
    roles=["admin", "staff"],
)


def get_current_user(
    request: Request, settings: Settings = Depends(get_settings)
) -> CurrentUser:
    """Resolve the caller from a Bearer JWT issued by P1's auth module.
    [PROPOSED] claims shape: {sub: user_id, email, roles: [...]}."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        if settings.AUTH_DEV_BYPASS:
            return DEV_USER
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


def get_notification_customer_id(db: Session, user: CurrentUser) -> uuid.UUID:
    if "customer" not in user.roles:
        return user.id

    from .modules.auth.models import Customer

    customer_id = db.scalar(
        sa.select(Customer.id).where(Customer.user_id == user.id)
    )
    if customer_id is None:
        raise AppError(
            "CUSTOMER_NOT_FOUND",
            "Customer account is not linked to a billing customer",
            404,
        )
    return customer_id


def require_roles(*roles: str):
    """Role names (P1): admin / staff / customer."""

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


# --- Module providers (P1/P2/P3 contracts) -----------------------------------
# USE_STUB_PROVIDERS=true  -> in-memory demo data (stubs), no P1/P3 tables needed.
# USE_STUB_PROVIDERS=false -> real DB providers: P2's catalog is live now;
#                             P1/P3 tables must exist (contract schema, doc §7).

_settings = get_settings()
if _settings.USE_STUB_PROVIDERS:
    _pricing = StubPricingProvider()
    _customers = StubCustomerProvider()
    _subscriptions = StubSubscriptionProvider(_customers)
else:
    _pricing = DbPricingProvider(SessionLocal)
    _customers = DbCustomerProvider(SessionLocal)
    _subscriptions = DbSubscriptionProvider(SessionLocal)


def get_pricing_provider():
    return _pricing


def get_customer_provider():
    return _customers


def get_subscription_provider():
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


# --- Phase 2 (P4): finance intelligence providers -----------------------------
# LLM provider + P2/P3 analytics contracts consumed by the copilot. The
# analytics factories return DB implementations until P2/P3 ship native
# services — swap them here and the copilot stays unchanged.

from .modules.finance_intelligence.ai.provider import (  # noqa: E402
    RateLimiter,
    build_provider,
)
from .modules.finance_intelligence.integrations import (  # noqa: E402
    DbProductAnalyticsProvider,
    DbSubscriptionAnalyticsProvider,
)

_llm = build_provider(_settings)
_rate_limiter = RateLimiter(_settings.AI_RATE_LIMIT_PER_MINUTE)
_product_analytics = DbProductAnalyticsProvider()
_subscription_analytics = DbSubscriptionAnalyticsProvider()


def get_llm_provider():
    return _llm


def get_rate_limiter():
    return _rate_limiter


def get_product_analytics_provider():
    return _product_analytics


def get_subscription_analytics_provider():
    return _subscription_analytics


DbDep = Depends(get_db)
