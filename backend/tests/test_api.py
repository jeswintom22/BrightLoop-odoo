import pytest
from fastapi.testclient import TestClient

from app import deps
from app.main import create_app
from app.modules.billing.service_billing import BillingService
from app.modules.billing.service_payments import PaymentService


@pytest.fixture()
def client(session_factory, providers):
    app = create_app()

    def test_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[deps.get_db] = test_db
    app.dependency_overrides[deps.get_session_factory] = lambda: session_factory
    app.dependency_overrides[deps.get_billing_service] = lambda: BillingService(
        pricing=providers["pricing"],
        subscriptions=providers["subs"],
        customers=providers["customers"],
    )
    app.dependency_overrides[deps.get_subscription_provider] = (
        lambda: providers["subs"]
    )
    app.dependency_overrides[deps.get_customer_provider] = (
        lambda: providers["customers"]
    )
    app.dependency_overrides[deps.get_pricing_provider] = (
        lambda: providers["pricing"]
    )
    return TestClient(app)


def test_internal_run_requires_token(client):
    r = client.post("/api/v1/internal/billing/run", json={})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_internal_run_with_token_generates_invoices(client, providers):
    r = client.post(
        "/api/v1/internal/billing/run",
        json={},
        headers={"X-Internal-Token": "dev-internal-token"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["generated"] == 4
    assert body["remaining"] == 0
    assert body["trigger_source"] == "scheduled"


def test_invoice_lifecycle_over_api(client, providers):
    # generate via run, then list + confirm + pay + verify paid
    client.post(
        "/api/v1/internal/billing/run",
        json={},
        headers={"X-Internal-Token": "dev-internal-token"},
    )
    r = client.get("/api/v1/invoices")
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 4
    inv = page["items"][0]
    assert inv["status"] == "draft"

    r = client.post(f"/api/v1/invoices/{inv['id']}/confirm")
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"

    r = client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv["id"],
            "amount": str(inv["total_amount"]),
            "method": "upi",
            "idempotency_key": "api-test-1",
        },
    )
    assert r.status_code == 201

    r = client.get(f"/api/v1/invoices/{inv['id']}")
    assert r.json()["status"] == "paid"
    assert r.json()["outstanding"] in ("0", "0.00", 0, 0.0)


def test_manual_invoice_create_then_conflict(client, providers):
    from app.core.time import business_date

    sub = providers["subs"].get_due_subscriptions(business_date(), limit=1)[0]
    r = client.post("/api/v1/invoices", json={"subscription_id": str(sub.id)})
    assert r.status_code == 201
    inv = r.json()

    # same explicit period -> 409 with existing id
    r2 = client.post(
        "/api/v1/invoices",
        json={
            "subscription_id": str(sub.id),
            "period_start": inv["period_start"],
            "period_end": inv["period_end"],
        },
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "INVOICE_ALREADY_EXISTS"


def test_dashboard_summary_shape(client):
    client.post(
        "/api/v1/internal/billing/run",
        json={},
        headers={"X-Internal-Token": "dev-internal-token"},
    )
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "active_subscriptions",
        "revenue_received",
        "outstanding_amount",
        "overdue_count",
        "overdue_amount",
        "draft_count",
        "recent_payments",
        "top_overdue",
    ):
        assert key in body
    assert body["draft_count"] == 4
    assert body["active_subscriptions"] == 6  # stub seed: 6 active (incl. expired)


def test_revenue_trend_shape(client):
    client.post(
        "/api/v1/internal/billing/run",
        json={},
        headers={"X-Internal-Token": "dev-internal-token"},
    )
    # invoices are drafts -> excluded from trend until confirmed
    r = client.get("/api/v1/dashboard/revenue-trend?interval=month")
    assert r.status_code == 200
    body = r.json()
    assert body["interval"] == "month"
    assert isinstance(body["points"], list)


def test_validation_error_envelope(client):
    r = client.post("/api/v1/payments", json={"invoice_id": "not-a-uuid"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invoice_pdf_endpoint(client, providers):
    from app.core.time import business_date

    sub = providers["subs"].get_due_subscriptions(business_date(), limit=1)[0]
    r = client.post("/api/v1/invoices", json={"subscription_id": str(sub.id)})
    inv_id = r.json()["id"]
    r = client.get(f"/api/v1/invoices/{inv_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
