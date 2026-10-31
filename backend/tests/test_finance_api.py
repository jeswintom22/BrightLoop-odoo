"""API-level checks: authz, rate limiting, endpoint wiring, risk explain."""

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

from app import deps
from app.deps import CurrentUser
from app.main import create_app
from app.modules.finance_intelligence.ai.provider import RateLimiter, TemplateProvider
from app.modules.finance_intelligence.integrations import (
    DbProductAnalyticsProvider,
    DbSubscriptionAnalyticsProvider,
)
from app.core.time import business_date

from finance_seed import customer, invoice, payment


@pytest.fixture()
def client(session_factory):
    app = create_app()

    def test_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[deps.get_db] = test_db
    app.dependency_overrides[deps.get_llm_provider] = lambda: TemplateProvider()
    app.dependency_overrides[deps.get_product_analytics_provider] = (
        lambda: DbProductAnalyticsProvider()
    )
    app.dependency_overrides[deps.get_subscription_analytics_provider] = (
        lambda: DbSubscriptionAnalyticsProvider()
    )
    return TestClient(app)


def test_mrr_endpoint_shape(client):
    r = client.get("/api/v1/finance-intelligence/revenue/mrr")
    assert r.status_code == 200
    body = r.json()
    for key in ("as_of", "mrr", "arr", "by_plan", "by_frequency", "subscription_count"):
        assert key in body


def test_copilot_endpoint_answers(client, session):
    today = business_date()
    c = customer(session)
    inv = invoice(session, customer=c, total="321.00", issue_date=today)
    payment(session, invoice=inv, amount="321.00")

    r = client.post(
        "/api/v1/finance-intelligence/copilot",
        json={"question": "How much revenue did we collect this month?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "321.00" in body["answer"]
    assert body["intent"] == "revenue_collected"


def test_customer_role_forbidden(client):
    customer_user = CurrentUser(
        id=uuid.uuid4(), email="cust@example.com", roles=["customer"]
    )
    client.app.dependency_overrides[deps.get_current_user] = lambda: customer_user
    r = client.get("/api/v1/finance-intelligence/revenue/mrr")
    assert r.status_code == 403
    r = client.post(
        "/api/v1/finance-intelligence/copilot",
        json={"question": "revenue?"},
    )
    assert r.status_code == 403
    client.app.dependency_overrides.pop(deps.get_current_user)


def test_rate_limit_returns_429(client):
    limiter = RateLimiter(2)
    client.app.dependency_overrides[deps.get_rate_limiter] = lambda: limiter
    for _ in range(2):
        assert client.post(
            "/api/v1/finance-intelligence/copilot", json={"question": "revenue this month?"}
        ).status_code == 200
    r = client.post(
        "/api/v1/finance-intelligence/copilot", json={"question": "revenue this month?"}
    )
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


def test_risks_and_explain_endpoints(client, session):
    today = business_date()
    c = customer(session, name="Risky Biz")
    invoice(session, customer=c, total="15000.00", due_date=today - dt.timedelta(days=10))

    r = client.get("/api/v1/finance-intelligence/risks")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total_risks"] >= 1
    idx = body["risks"][0]["risk_index"]

    r = client.post(
        "/api/v1/finance-intelligence/risks/explain",
        json={"risk_index": idx},
    )
    assert r.status_code == 200
    exp = r.json()
    assert "Risky Biz" in exp["explanation"]
    assert exp["provider"] == "template"


def test_risks_severity_filter(client, session):
    today = business_date()
    c = customer(session)
    invoice(session, customer=c, total="15000.00", due_date=today - dt.timedelta(days=10))

    r = client.get("/api/v1/finance-intelligence/risks?severity=high")
    assert r.status_code == 200
    assert all(x["severity"] == "high" for x in r.json()["risks"])


def test_summary_generate_and_list(client):
    r = client.post(
        "/api/v1/finance-intelligence/summaries/generate",
        json={"period_kind": "month"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "template"
    assert "PERFORMANCE" in body["summary_text"]

    r = client.get("/api/v1/finance-intelligence/summaries")
    assert r.status_code == 200
    page = r.json()
    assert page["total"] >= 1

    r = client.get(f"/api/v1/finance-intelligence/summaries/{body['id']}")
    assert r.status_code == 200


def test_revenue_trends_and_breakdown_endpoints(client):
    today = business_date()
    r = client.get(
        f"/api/v1/finance-intelligence/revenue/trends?interval=month&from={today - dt.timedelta(days=30)}&to={today}"
    )
    assert r.status_code == 200
    assert "growth_pct" in r.json()

    r = client.get(
        f"/api/v1/finance-intelligence/revenue/breakdown?by=plan&from={today - dt.timedelta(days=30)}&to={today}"
    )
    assert r.status_code == 200
    assert r.json()["by"] == "plan"


def test_forecast_endpoint(client):
    r = client.get("/api/v1/finance-intelligence/revenue/forecast?horizon_days=30")
    assert r.status_code == 200
    body = r.json()
    for key in ("expected_billings", "expected_collections", "collection_rate"):
        assert key in body
