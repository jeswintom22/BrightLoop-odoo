"""Tests for Product Performance Analytics, Discount Effectiveness, and AI Insights."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import deps
from app.main import create_app
from app.seed_analytics import run_seed


@pytest.fixture()
def client(session_factory, providers):
    app = create_app()

    # Seed the test session
    with session_factory() as s:
        run_seed(s)

    def test_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[deps.get_db] = test_db
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


def test_get_catalog_overview(client: TestClient):
    response = client.get("/api/v1/analytics/overview")
    assert response.status_code == 200
    data = response.json()

    assert data["total_products"] >= 7
    assert data["active_products"] >= 7
    assert data["total_variants"] >= 7
    assert data["total_plans"] >= 6
    assert data["total_invoiced_revenue"] > 0
    assert data["catalog_health_score"] > 0
    assert data["health_grade"] in ["A+", "A", "B", "C", "D"]


def test_get_product_performance(client: TestClient):
    response = client.get("/api/v1/analytics/performance")
    assert response.status_code == 200
    data = response.json()

    assert data["total_products"] >= 7
    items = data["items"]
    assert len(items) >= 7

    # Find Cloud ERP Pro
    erp = next((p for p in items if p["product_name"] == "Cloud ERP Pro"), None)
    assert erp is not None
    assert erp["sales_price"] == 3000.0
    assert erp["cost_price"] == 800.0
    assert erp["unit_margin"] == 2200.0
    assert erp["margin_pct"] > 70.0
    assert erp["profitability_tier"] == "High Margin (>50%)"

    # Find Legacy Storage Addon (negative margin)
    storage = next((p for p in items if p["product_name"] == "Legacy Storage Addon"), None)
    assert storage is not None
    assert storage["is_underperforming"] is True
    assert storage["cost_price"] > storage["sales_price"]
    assert storage["profitability_tier"] == "Loss Making (<0%)"


def test_get_top_subscribed(client: TestClient):
    response = client.get("/api/v1/analytics/top-subscribed")
    assert response.status_code == 200
    data = response.json()

    assert "products" in data
    assert "plans" in data
    assert len(data["products"]) > 0
    assert len(data["plans"]) > 0

    first_prod = data["products"][0]
    assert first_prod["rank"] == 1
    assert first_prod["active_subscribers"] >= 0

    first_plan = data["plans"][0]
    assert first_plan["rank"] == 1
    assert first_plan["mrr_equivalent"] >= 0


def test_get_top_variants(client: TestClient):
    response = client.get("/api/v1/analytics/top-variants")
    assert response.status_code == 200
    data = response.json()

    assert data["total_variants"] >= 7
    first_var = data["items"][0]
    assert "variant_name" in first_var
    assert "sales_price" in first_var
    assert "unit_margin" in first_var


def test_get_revenue_comparison(client: TestClient):
    response = client.get("/api/v1/analytics/revenue-comparison")
    assert response.status_code == 200
    data = response.json()

    assert len(data["products"]) > 0
    assert len(data["plans"]) > 0
    total_share = sum(p["revenue_share_pct"] for p in data["products"])
    assert 99.0 <= total_share <= 101.0  # approximate 100%


def test_get_discounts_analytics(client: TestClient):
    response = client.get("/api/v1/analytics/discounts")
    assert response.status_code == 200
    data = response.json()

    assert data["total_discounts"] >= 4
    assert data["active_discounts"] >= 3
    assert data["total_redemptions"] > 0
    assert data["total_savings_given"] > 0
    assert data["overall_roi_multiplier"] > 0

    # Test individual discount properties
    launch = next((d for d in data["items"] if d["code"] == "LAUNCH50"), None)
    assert launch is not None
    assert launch["usage_count"] == 82
    assert launch["usage_limit"] == 100
    assert launch["remaining_uses"] == 18
    assert launch["is_exhausted"] is False

    early = next((d for d in data["items"] if d["code"] == "EARLYBIRD"), None)
    assert early is not None
    assert early["is_exhausted"] is True
    assert early["availability_status"] == "Exhausted"

    flat = next((d for d in data["items"] if d["code"] == "FLAT500"), None)
    assert flat is not None
    assert flat["availability_status"] == "Near Capacity"


def test_get_underperforming_products(client: TestClient):
    response = client.get("/api/v1/analytics/underperforming")
    assert response.status_code == 200
    data = response.json()

    assert data["total_underperforming"] >= 2
    assert data["high_severity_count"] >= 1

    # Legacy Storage should be HIGH severity
    storage = next((u for u in data["items"] if u["product_name"] == "Legacy Storage Addon"), None)
    assert storage is not None
    assert storage["severity"] == "HIGH"
    assert len(storage["issues"]) > 0
    assert len(storage["recommendations"]) > 0


def test_get_product_profitability(client: TestClient):
    response = client.get("/api/v1/analytics/profitability")
    assert response.status_code == 200
    data = response.json()

    assert data["total_catalog_revenue"] > 0
    assert data["total_catalog_cost"] > 0
    assert data["total_catalog_profit"] > 0
    assert data["catalog_margin_pct"] > 0
    assert len(data["items"]) >= 7


def test_get_performance_trends(client: TestClient):
    response = client.get("/api/v1/analytics/trends?interval=month")
    assert response.status_code == 200
    data = response.json()

    assert data["interval"] == "month"
    assert len(data["points"]) > 0
    p1 = data["points"][0]
    assert "period" in p1
    assert "total_revenue" in p1
    assert "net_profit" in p1


def test_generate_ai_insights(client: TestClient):
    response = client.get("/api/v1/analytics/ai-insights")
    assert response.status_code == 200
    data = response.json()

    assert data["catalog_health_score"] > 0
    assert len(data["executive_summary"]) > 20
    assert len(data["top_performers_summary"]) > 10
    assert len(data["underperforming_warnings"]) > 0
    assert len(data["actionable_recommendations"]) > 0
    assert "generated_by" in data


def test_openapi_integration_guide(client: TestClient):
    response = client.get("/api/v1/analytics/openapi-spec")
    assert response.status_code == 200
    data = response.json()

    assert "openapi_json_url" in data
    assert len(data["endpoints"]) == 10
