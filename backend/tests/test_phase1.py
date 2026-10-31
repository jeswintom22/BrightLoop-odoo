"""Phase 1 verification — P1 auth/RBAC, P3 lifecycle, real-provider billing E2E.

Uses the REAL modules (no stubs): auth service/models, subscription service,
and Db* providers against the shared Base schema.
"""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa

from app import deps
from app.core.time import business_date, utc_now
from app.main import create_app
from app.modules.auth import security as sec
from app.modules.auth.models import Customer, PasswordResetToken, User
from app.modules.billing.integrations_db import (
    DbCustomerProvider,
    DbPricingProvider,
    DbSubscriptionProvider,
)
from app.modules.billing.models import Invoice
from app.modules.billing.service_billing import BillingService
from app.modules.billing.service_payments import PaymentService
from app.modules.subscriptions import service_subscriptions as subsvc
from app.modules.subscriptions.models import Subscription, SubscriptionItem


@pytest.fixture()
def client(session_factory):
    """API client wired to the test DB — real providers via get_db override."""
    app = create_app()

    def test_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[deps.get_db] = test_db
    app.dependency_overrides[deps.get_session_factory] = lambda: session_factory
    app.dependency_overrides[deps.get_pricing_provider] = (
        lambda: DbPricingProvider(session_factory)
    )
    app.dependency_overrides[deps.get_customer_provider] = (
        lambda: DbCustomerProvider(session_factory)
    )
    app.dependency_overrides[deps.get_subscription_provider] = (
        lambda: DbSubscriptionProvider(session_factory)
    )
    return TestClient(app)


def _user(session, email, role, password="Str0ng!Pass"):
    u = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=sec.hash_password(password),
        full_name=email.split("@")[0].title(),
        role=role,
        is_active=True,
    )
    session.add(u)
    session.flush()
    return u


def _login(client, email, password="Str0ng!Pass"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- P1: auth & RBAC ----------------------------------------------------------

def test_register_login_me(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "alice@example.com",
            "password": "Str0ng!Pass",
            "full_name": "Alice",
        },
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    r = client.get("/api/v1/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["role"] == "customer"
    assert r.json()["customer_id"] is not None


def test_duplicate_email_rejected(client):
    payload = {
        "email": "dup@example.com",
        "password": "Str0ng!Pass",
        "full_name": "Dup",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code in (400, 409), r.text


@pytest.mark.parametrize(
    "pw", ["short", "8Char!Aa", "alllowercase1!", "ALLUPPER1!", "NoSpecial123"]
)
def test_password_policy(client, pw):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": f"{pw}@x.com", "password": pw, "full_name": "T"},
    )
    assert r.status_code in (400, 422), f"{pw!r} accepted: {r.text}"


def test_wrong_password_rejected(client, session):
    _user(session, "bob@example.com", "customer")
    session.commit()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "Wr0ng!Pass"},
    )
    assert r.status_code == 401


def test_staff_creation_admin_only(client, session):
    admin = _user(session, "admin@x.com", "admin")
    staff = _user(session, "staff@x.com", "staff")
    cust = _user(session, "cust@x.com", "customer")
    session.commit()
    for u, expected in ((admin, 201), (staff, 403), (cust, 403)):
        token = sec.issue_token(u)
        r = client.post(
            "/api/v1/users/staff",
            json={"email": f"new-{u.role}@x.com", "password": "Str0ng!Pass", "full_name": "N"},
            headers=_auth(token),
        )
        assert r.status_code == expected, (u.role, r.status_code, r.text)


def test_customer_cannot_hit_staff_endpoints(client, session):
    cust = _user(session, "c@x.com", "customer")
    session.commit()
    r = client.get("/api/v1/dashboard/summary", headers=_auth(sec.issue_token(cust)))
    assert r.status_code == 403
    r = client.get("/api/v1/invoices", headers=_auth(sec.issue_token(cust)))
    assert r.status_code == 403


def test_forgot_password_no_enumeration(client, session):
    _user(session, "known@x.com", "customer")
    session.commit()
    r1 = client.post("/api/v1/auth/forgot-password", json={"email": "known@x.com"})
    r2 = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@x.com"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()


def test_reset_token_single_use_and_expiry(client, session):
    u = _user(session, "rst@x.com", "customer")
    session.commit()
    from app.modules.auth import service as authsvc

    raw = authsvc.request_password_reset(session, email="rst@x.com")
    session.commit()
    assert raw
    r = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "N3w!Passw0rd"},
    )
    assert r.status_code == 200, r.text
    _login(client, "rst@x.com", "N3w!Passw0rd")
    # reuse → rejected
    r = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "0ther!Passw0rd"},
    )
    assert r.status_code in (400, 401, 404)
    # expired token → rejected
    raw2 = authsvc.request_password_reset(session, email="rst@x.com")
    session.execute(
        sa.update(PasswordResetToken)
        .where(PasswordResetToken.user_id == u.id)
        .values(expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1))
    )
    session.commit()
    r = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw2, "new_password": "0ther!Passw0rd"},
    )
    assert r.status_code in (400, 401, 404)


def test_portal_ownership_isolation(client, session):
    """Customer A must never see customer B's invoices."""
    ua = _user(session, "a@x.com", "customer")
    ub = _user(session, "b@x.com", "customer")
    ca = Customer(id=uuid.uuid4(), user_id=ua.id, name="A", email="a@x.com")
    cb = Customer(id=uuid.uuid4(), user_id=ub.id, name="B", email="b@x.com")
    session.add_all([ca, cb])
    session.flush()
    today = business_date()
    inv_b = Invoice(
        id=uuid.uuid4(),
        invoice_number="INV-2026-999999",
        customer_id=cb.id,
        status="confirmed",
        issue_date=today,
        due_date=today + dt.timedelta(days=7),
        period_start=today,
        period_end=today + dt.timedelta(days=30),
        currency="INR",
        subtotal=Decimal("100"),
        tax_total=Decimal("0"),
        discount_total=Decimal("0"),
        total_amount=Decimal("100"),
        amount_paid=Decimal("0"),
    )
    session.add(inv_b)
    session.commit()

    ta = _auth(sec.issue_token(ua))
    r = client.get("/api/v1/portal/invoices", headers=ta)
    assert r.status_code == 200
    assert all(i["invoice_number"] != "INV-2026-999999" for i in r.json()["items"])
    r = client.get(f"/api/v1/portal/invoices/{inv_b.id}", headers=ta)
    assert r.status_code in (403, 404), r.text
    # staff role can't use portal either
    staff = _user(session, "s@x.com", "staff")
    session.commit()
    r = client.get("/api/v1/portal/invoices", headers=_auth(sec.issue_token(staff)))
    assert r.status_code == 403


# --- P3: quotation → subscription lifecycle -----------------------------------

def _catalog_seed(session):
    """Minimal P2 catalog: product + plan (int PKs, real models)."""
    from app.models.product import Product
    from app.models.subscription_plan import SubscriptionPlan

    p = Product(name="Widget", product_type="service", sales_price=Decimal("200"),
                cost_price=Decimal("80"), is_active=True)
    session.add(p)
    session.flush()
    plan = SubscriptionPlan(
        name="Monthly", product_id=p.id, price=Decimal("200"),
        billing_frequency="monthly", minimum_quantity=1,
        start_date=business_date() - dt.timedelta(days=1),
        status="active", allow_pause=True, allow_renewal=True,
        allow_early_closure=True, auto_closure=True,
    )
    session.add(plan)
    session.flush()
    return p, plan


def test_quotation_to_active_subscription(client, session):
    _user(session, "staff1@x.com", "staff")
    cust = _user(session, "qc@x.com", "customer")
    c = Customer(id=uuid.uuid4(), user_id=cust.id, name="QC", email="qc@x.com")
    session.add(c)
    p, plan = _catalog_seed(session)
    session.commit()
    tok = _auth(sec.issue_token(_user(session, "staff2@x.com", "staff")))
    session.commit()

    r = client.post(
        "/api/v1/quotation-templates",
        json={
            "name": "Std",
            "validity_days": 10,
            "lines": [{"product_id": p.id, "plan_id": plan.id, "quantity": "2"}],
        },
        headers=tok,
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = client.post(
        "/api/v1/quotations", json={"customer_id": str(c.id), "template_id": tid},
        headers=tok,
    )
    assert r.status_code == 201, r.text
    qid = r.json()["id"]
    assert r.json()["status"] == "draft"
    assert Decimal(r.json()["total_amount"]) > 0

    r = client.post(f"/api/v1/quotations/{qid}/confirm", headers=tok)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/quotations/{qid}/convert", json={}, headers=tok)
    assert r.status_code in (200, 201), r.text
    sub = r.json()
    assert sub["status"] in ("confirmed", "active")
    assert sub["subscription_number"].startswith("SUB-")

    if sub["status"] != "active":
        r = client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=tok)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "active"
    else:
        # already active → re-activate is an invalid transition
        r = client.post(f"/api/v1/subscriptions/{sub['id']}/activate", headers=tok)
        assert r.status_code in (400, 409)


def test_expired_quotation_rejected(client, session):
    _user(session, "st@x.com", "staff")
    session.commit()
    tok = _auth(sec.issue_token(session.query(User).filter_by(email="st@x.com").one()))
    p, plan = _catalog_seed(session)
    cust = _user(session, "e@x.com", "customer")
    c = Customer(id=uuid.uuid4(), user_id=cust.id, name="E", email="e@x.com")
    session.add(c)
    session.commit()
    r = client.post(
        "/api/v1/quotations",
        json={
            "customer_id": str(c.id),
            "lines": [{"product_id": p.id, "plan_id": plan.id, "quantity": "1"}],
        },
        headers=tok,
    )
    qid = r.json()["id"]
    session.execute(
        sa.update(subsvc.Quotation)
        .where(subsvc.Quotation.id == uuid.UUID(qid))
        .values(valid_until=business_date() - dt.timedelta(days=1))
    )
    session.commit()
    r = client.post(f"/api/v1/quotations/{qid}/confirm", headers=tok)
    assert r.status_code in (400, 409, 422), r.text


def test_lifecycle_pause_blocks_billing(client, session, session_factory):
    """Paused sub → not due; resumed → due again; closed → never due."""
    _user(session, "lc@x.com", "staff")
    session.commit()
    u = session.query(User).filter_by(email="lc@x.com").one()
    tok = _auth(sec.issue_token(u))
    cust = _user(session, "lc2@x.com", "customer")
    c = Customer(id=uuid.uuid4(), user_id=cust.id, name="LC", email="lc2@x.com")
    session.add(c)
    session.flush()
    today = business_date()
    sub = Subscription(
        id=uuid.uuid4(),
        subscription_number="SUB-2026-000001",
        customer_id=c.id,
        status="active",
        billing_frequency="monthly",
        start_date=today - dt.timedelta(days=30),
        next_billing_date=today,
    )
    session.add(sub)
    session.commit()
    sid = str(sub.id)

    prov = DbSubscriptionProvider(session_factory)
    assert prov.count_due(today) == 1

    r = client.post(f"/api/v1/subscriptions/{sid}/pause", headers=tok)
    assert r.status_code == 200, r.text
    assert prov.count_due(today) == 0  # paused → never billed

    r = client.post(f"/api/v1/subscriptions/{sid}/resume", headers=tok)
    assert r.status_code == 200, r.text
    assert prov.count_due(today) == 1

    r = client.post(f"/api/v1/subscriptions/{sid}/close", headers=tok)
    assert r.status_code == 200, r.text
    assert prov.count_due(today) == 0  # closed → never billed
    # invalid transition: resume a closed sub
    r = client.post(f"/api/v1/subscriptions/{sid}/resume", headers=tok)
    assert r.status_code in (400, 409, 422)


def test_renew_extends_expiry(client, session):
    _user(session, "rn@x.com", "staff")
    session.commit()
    u = session.query(User).filter_by(email="rn@x.com").one()
    tok = _auth(sec.issue_token(u))
    cust = _user(session, "rn2@x.com", "customer")
    c = Customer(id=uuid.uuid4(), user_id=cust.id, name="RN", email="rn2@x.com")
    session.add(c)
    session.flush()
    today = business_date()
    sub = Subscription(
        id=uuid.uuid4(),
        subscription_number="SUB-2026-000002",
        customer_id=c.id,
        status="active",
        billing_frequency="yearly",
        start_date=today - dt.timedelta(days=400),
        next_billing_date=today,
        expiry_date=today + dt.timedelta(days=5),
    )
    session.add(sub)
    session.commit()
    old_expiry = sub.expiry_date
    r = client.post(f"/api/v1/subscriptions/{sub.id}/renew", headers=tok)
    assert r.status_code == 200, r.text
    assert dt.date.fromisoformat(r.json()["expiry_date"]) > old_expiry


# --- P2→P4 real-provider E2E: pricing + tax + discount → invoice → payment ---

def test_real_provider_billing_e2e(session, session_factory):
    """Full flow with REAL modules: P1 customer + P2 catalog + P3 sub →
    invoice (tax + discount from catalog) → payment → balances."""
    from app.models.discount import Discount
    from app.models.product import Product
    from app.models.tax import TaxConfiguration

    today = business_date()
    tax = TaxConfiguration(name="GST", tax_percentage=Decimal("18"), is_active=True)
    prod = Product(name="Suite", product_type="service",
                   sales_price=Decimal("1000"), cost_price=Decimal("400"),
                   tax_id=None, is_active=True)
    disc = Discount(
        name="Flat 100", code="FLAT100", discount_type="fixed_amount",
        discount_value=Decimal("100"),
        start_date=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
        expiry_date=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30),
        is_active=True, min_purchase_amount=Decimal("0"),
    )
    session.add_all([tax, prod, disc])
    session.flush()
    prod.tax_id = tax.id
    disc.applicable_products.append(prod)

    cust = Customer(id=uuid.uuid4(), name="Real Cust", email="rc@x.com")
    sub = Subscription(
        id=uuid.uuid4(),
        subscription_number="SUB-2026-000100",
        customer_id=cust.id,
        status="active",
        billing_frequency="monthly",
        start_date=today - dt.timedelta(days=30),
        next_billing_date=today,
    )
    item = SubscriptionItem(
        id=uuid.uuid4(), subscription_id=sub.id, product_id=prod.id,
        description="Suite seat", quantity=Decimal("2"),
        unit_price=Decimal("1000"),
    )
    session.add_all([cust, sub, item])
    session.commit()

    billing = BillingService(
        pricing=DbPricingProvider(session_factory),
        subscriptions=DbSubscriptionProvider(session_factory),
        customers=DbCustomerProvider(session_factory),
    )
    run = billing.execute_run(session_factory, run_for_date=today)
    assert run.generated == 1, f"errors={getattr(run, 'errors', None)}"
    # duplicate run → no second invoice (idempotent)
    run2 = billing.execute_run(session_factory, run_for_date=today)
    assert run2.generated == 0

    inv = session.query(Invoice).one()
    assert inv.subscription_id == sub.id
    assert inv.customer_id == cust.id
    # 2×1000 = 2000 subtotal; 18% tax on (2000-100) = 342; total = 2000+342-100 = 2242
    assert inv.subtotal == Decimal("2000")
    assert inv.discount_total == Decimal("100")
    assert inv.tax_total == Decimal("342")
    assert inv.total_amount == Decimal("2242")
    # next billing advanced one month
    session.refresh(sub)
    assert sub.next_billing_date > today

    # confirm → pay partial → still outstanding → pay rest → paid
    inv.status = "confirmed"
    session.commit()
    pay = PaymentService()
    with session_factory() as s:
        pay.record_payment(
            s, invoice_id=inv.id, amount=Decimal("1242"),
            method="bank_transfer", paid_at=utc_now(),
            idempotency_key="e2e-1",
        )
        s.commit()
    session.refresh(inv)
    assert inv.status == "confirmed"
    assert inv.amount_paid == Decimal("1242")
    with session_factory() as s:
        pay.record_payment(
            s, invoice_id=inv.id, amount=Decimal("1000"),
            method="bank_transfer", paid_at=utc_now(),
            idempotency_key="e2e-2",
        )
        s.commit()
    session.refresh(inv)
    assert inv.status == "paid"
    assert inv.amount_paid == inv.total_amount


def test_expired_subscription_auto_closed(session, session_factory):
    today = business_date()
    cust = Customer(id=uuid.uuid4(), name="X", email="x@x.com")
    sub = Subscription(
        id=uuid.uuid4(), subscription_number="SUB-2026-000200",
        customer_id=cust.id, status="active", billing_frequency="monthly",
        start_date=today - dt.timedelta(days=60), next_billing_date=today,
        expiry_date=today - dt.timedelta(days=1),
    )
    session.add_all([cust, sub])
    session.commit()
    with session_factory() as s:
        n = subsvc.close_expired(s, as_of=today)
        s.commit()
    assert n == 1
    session.refresh(sub)
    assert sub.status == "closed"
