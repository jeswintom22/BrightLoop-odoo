import os

# Tests must never touch the dev/prod database — force the default engine
# (app.db.session) onto a dedicated file before any app module imports bind it.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register P2 catalog tables
import app.modules.auth.models  # noqa: F401 — P1 tables
import app.modules.subscriptions.models  # noqa: F401 — P3 tables
from app.core.time import business_date
from app.core.database import Base
from app.modules.billing import models  # noqa: F401 — register P4 billing tables
from app.modules.finance_intelligence import models as _fi_models  # noqa: F401 — register financial_summaries
from app.modules.billing.integrations_stub import (
    StubCustomerProvider,
    StubPricingProvider,
    StubSubscriptionProvider,
)
from app.modules.billing.service_billing import BillingService
from app.modules.billing.service_payments import PaymentService


@pytest.fixture(scope="session", autouse=True)
def _prepare_default_db():
    """Service-level tests (e.g. products) use the default SessionLocal —
    ensure the shared schema exists there (fresh per run)."""
    from app.db.session import engine as default_engine

    Base.metadata.drop_all(default_engine)
    Base.metadata.create_all(default_engine)
    yield


@pytest.fixture()
def engine():
    eng = sa.create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def session(session_factory):
    s = session_factory()
    yield s
    s.close()


@pytest.fixture()
def providers():
    customers = StubCustomerProvider()
    subs = StubSubscriptionProvider(customers)
    pricing = StubPricingProvider()
    return {"customers": customers, "subs": subs, "pricing": pricing}


@pytest.fixture()
def billing(providers):
    return BillingService(
        pricing=providers["pricing"],
        subscriptions=providers["subs"],
        customers=providers["customers"],
    )


@pytest.fixture()
def payment_service():
    return PaymentService()


@pytest.fixture()
def confirmed_invoice(billing, session, providers):
    sub = providers["subs"].get_due_subscriptions(business_date(), limit=1)[0]
    invoice, _ = billing.generate_invoice(session, subscription_id=sub.id)
    billing.confirm_invoice(session, invoice)
    session.commit()
    return invoice
