import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.time import business_date
from app.core.database import Base
from app.modules.billing import models  # noqa: F401 — register tables
from app.modules.billing.integrations_stub import (
    StubCustomerProvider,
    StubPricingProvider,
    StubSubscriptionProvider,
)
from app.modules.billing.service_billing import BillingService
from app.modules.billing.service_payments import PaymentService


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
