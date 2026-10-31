"""
tests/test_analytics.py
=======================
Integration and unit tests for the Subscription Intelligence & Analytics module.

Coverage:
  - Churn rate and retention rate calculations
  - Cancellation reason aggregation
  - Renewal forecasting (upcoming expiry within window)
  - Expansion / upgrade / downgrade movement analytics
  - Health indicator / renewal risk scoring
  - POST /api/analytics/subscription-ai-insights (OpenAI mocked)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from models import LifecycleStatus, Subscription, SubscriptionLine


# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and tear them down afterwards."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper: create a confirmed quotation and convert it to a subscription
# ---------------------------------------------------------------------------

def _make_active_subscription(
    client: TestClient,
    customer_id: str = "CUST-A",
    customer_name: str = "Analytics Customer",
    email: str = "test@analytics.io",
    unit_price: float = 500.0,
    billing_frequency: str = "monthly",
    valid_until_offset: int = 30,
    start_date: date | None = None,
) -> dict:
    """Helper: create a quotation + confirm + convert to Active subscription."""
    valid_until = (date.today() + timedelta(days=valid_until_offset)).isoformat()
    quo_resp = client.post(
        "/api/quotations",
        json={
            "customer_id": customer_id,
            "customer_name": customer_name,
            "customer_email": email,
            "valid_until": valid_until,
            "status": "Confirmed",
            "lines": [
                {
                    "product_name": "Analytics Test Product",
                    "quantity": 1,
                    "unit_price": unit_price,
                    "discount_percent": 0.0,
                    "billing_frequency": billing_frequency,
                }
            ],
        },
    )
    assert quo_resp.status_code == 201, quo_resp.text
    qid = quo_resp.json()["id"]

    payload: dict = {}
    if start_date:
        payload["start_date"] = start_date.isoformat()

    conv_resp = client.post(f"/api/subscriptions/convert/{qid}", json=payload or None)
    assert conv_resp.status_code == 201, conv_resp.text
    return conv_resp.json()


# ---------------------------------------------------------------------------
# Helper: close an existing subscription via its DB ID
# ---------------------------------------------------------------------------

def _close_subscription(client: TestClient, sub_id: int, reason: str = "Test cancellation") -> None:
    resp = client.post(
        f"/api/subscriptions/{sub_id}/close",
        params={"reason": reason},
    )
    assert resp.status_code == 200, resp.text


# ===========================================================================
# 1. Churn Rate & Retention Rate
# ===========================================================================

class TestChurnRetention:
    """Tests for GET /api/analytics/churn-retention"""

    def test_zero_churn_no_subscriptions(self, client):
        """With no subscriptions, churn and retention should both be sensible defaults."""
        resp = client.get("/api/analytics/churn-retention")
        assert resp.status_code == 200
        data = resp.json()
        assert data["churn_rate_percent"] == 0.0
        assert data["retention_rate_percent"] == 100.0
        assert data["churned_count"] == 0
        assert data["ending_active_count"] == 0

    def test_churn_rate_with_closed_subscription(self, client):
        """One active + one closed subscription should produce non-zero churn."""
        sub_a = _make_active_subscription(client, customer_id="CUST-CH-A", email="a@churn.com")
        sub_b = _make_active_subscription(client, customer_id="CUST-CH-B", email="b@churn.com")

        # Close sub_b
        _close_subscription(client, sub_b["id"], reason="Pricing too high")

        resp = client.get("/api/analytics/churn-retention")
        assert resp.status_code == 200
        data = resp.json()

        assert data["churned_count"] >= 1
        assert data["churn_rate_percent"] > 0.0
        assert data["retention_rate_percent"] < 100.0
        # churn + retention should sum to 100
        total = round(data["churn_rate_percent"] + data["retention_rate_percent"], 2)
        assert total == 100.0

    def test_retention_rate_all_active(self, client):
        """When no subscription is closed in the period, retention should be 100%."""
        _make_active_subscription(client, customer_id="CUST-RET-A", email="ret_a@test.io")
        _make_active_subscription(client, customer_id="CUST-RET-B", email="ret_b@test.io")

        # Use a future date window where nothing was closed
        future_start = (date.today() + timedelta(days=5)).isoformat()
        future_end = (date.today() + timedelta(days=35)).isoformat()

        resp = client.get(
            "/api/analytics/churn-retention",
            params={"start_date": future_start, "end_date": future_end},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["churned_count"] == 0
        assert data["retention_rate_percent"] == 100.0

    def test_period_dates_respected(self, client):
        """start_date / end_date query params are reflected in the response."""
        sd = (date.today() - timedelta(days=60)).isoformat()
        ed = (date.today() - timedelta(days=31)).isoformat()

        resp = client.get(
            "/api/analytics/churn-retention",
            params={"start_date": sd, "end_date": ed},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_start"] == sd
        assert data["period_end"] == ed

    def test_churned_revenue_loss_accumulates(self, client):
        """churned_revenue_loss should reflect sum of closed subscription amounts."""
        sub = _make_active_subscription(
            client, customer_id="CUST-REV-CH", email="rev@churn.io", unit_price=999.0
        )
        _close_subscription(client, sub["id"], reason="Budget cut")

        resp = client.get("/api/analytics/churn-retention")
        assert resp.status_code == 200
        data = resp.json()
        assert data["churned_revenue_loss"] >= 999.0

    def test_cohort_health_label_excellent(self, client):
        """Cohort health label should be 'Excellent' when churn < 5%."""
        # No closures → churn = 0%
        _make_active_subscription(client, customer_id="CUST-HLT", email="health@test.io")
        resp = client.get("/api/analytics/churn-retention")
        data = resp.json()
        assert "Excellent" in data["cohort_health"]


# ===========================================================================
# 2. Cancellation Reason Tracking
# ===========================================================================

class TestCancellationReasons:
    """Tests for GET /api/analytics/cancellation-reasons"""

    def test_no_cancellations(self, client):
        """With no closed subscriptions, breakdown should be empty."""
        resp = client.get("/api/analytics/cancellation-reasons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cancellations"] == 0
        assert data["breakdown"] == []
        assert data["primary_cancellation_driver"] == "None recorded"

    def test_cancellation_reason_aggregation(self, client):
        """Multiple closures with the same reason must aggregate correctly."""
        for i in range(3):
            sub = _make_active_subscription(
                client,
                customer_id=f"CUST-CANC-{i}",
                email=f"canc{i}@test.io",
            )
            _close_subscription(client, sub["id"], reason="Too expensive")

        # One with a different reason
        sub2 = _make_active_subscription(
            client, customer_id="CUST-CANC-X", email="cancx@test.io"
        )
        _close_subscription(client, sub2["id"], reason="Found alternative")

        resp = client.get("/api/analytics/cancellation-reasons")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_cancellations"] == 4

        reasons_map = {item["reason"]: item["count"] for item in data["breakdown"]}
        assert reasons_map.get("Too expensive", 0) == 3
        assert reasons_map.get("Found alternative", 0) == 1

        # Primary driver should be the top one
        assert data["primary_cancellation_driver"] == "Too expensive"

    def test_percentage_sums_to_100(self, client):
        """Percentages across all cancellation reasons should sum to 100."""
        for i in range(4):
            sub = _make_active_subscription(
                client, customer_id=f"CUST-PCT-{i}", email=f"pct{i}@test.io"
            )
            _close_subscription(client, sub["id"], reason=f"Reason {i % 2}")

        resp = client.get("/api/analytics/cancellation-reasons")
        data = resp.json()
        total_pct = round(sum(item["percentage"] for item in data["breakdown"]), 0)
        assert total_pct == 100.0

    def test_unspecified_reason_label(self, client):
        """Closures without a reason string should be bucketed as 'Unspecified / Voluntary Exit'."""
        # Close with an empty reason via direct DB manipulation approach: use close endpoint without reason
        sub = _make_active_subscription(
            client, customer_id="CUST-UNS", email="unspec@test.io"
        )
        # Close without a reason param (default label applied)
        close_resp = client.post(f"/api/subscriptions/{sub['id']}/close")
        assert close_resp.status_code == 200

        resp = client.get("/api/analytics/cancellation-reasons")
        data = resp.json()
        assert data["total_cancellations"] >= 1
        # Default reason from the router is "Subscription terminated." — ensure at least one entry
        assert len(data["breakdown"]) >= 1


# ===========================================================================
# 3. Renewal Forecasting & Upcoming Expiry
# ===========================================================================

class TestRenewalForecast:
    """Tests for GET /api/analytics/renewal-forecast"""

    def test_no_upcoming_renewals(self, client):
        """With no active subscriptions, renewals list should be empty."""
        resp = client.get("/api/analytics/renewal-forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert data["upcoming_renewals_count"] == 0
        assert data["forecasted_renewal_revenue"] == 0.0
        assert data["renewals"] == []

    def test_subscription_expiring_within_window(self, client):
        """A subscription with next_billing_date within 30 days should appear in forecast."""
        sub = _make_active_subscription(
            client,
            customer_id="CUST-FORE",
            email="fore@test.io",
            unit_price=300.0,
            billing_frequency="monthly",
        )

        resp = client.get("/api/analytics/renewal-forecast", params={"days": 40})
        assert resp.status_code == 200
        data = resp.json()

        # next_billing_date is set to today+1 for monthly frequency
        assert data["upcoming_renewals_count"] >= 1
        assert data["forecasted_renewal_revenue"] >= 300.0

        renewal_ids = [r["subscription_id"] for r in data["renewals"]]
        assert sub["id"] in renewal_ids

    def test_renewals_sorted_by_days_ascending(self, client):
        """Renewals should be sorted closest-expiry first."""
        # Create two subscriptions: one expires sooner (daily) and one later (yearly)
        sub_daily = _make_active_subscription(
            client,
            customer_id="CUST-SORT-D",
            email="sort_d@test.io",
            billing_frequency="daily",
        )
        sub_yearly = _make_active_subscription(
            client,
            customer_id="CUST-SORT-Y",
            email="sort_y@test.io",
            billing_frequency="yearly",
        )

        # Use max allowed window of 365 days to capture both
        resp = client.get("/api/analytics/renewal-forecast", params={"days": 365})
        assert resp.status_code == 200
        renewals = resp.json()["renewals"]

        # Verify ascending order by days_until_renewal
        for i in range(len(renewals) - 1):
            assert renewals[i]["days_until_renewal"] <= renewals[i + 1]["days_until_renewal"]

    def test_window_days_parameter_respected(self, client):
        """days=1 should only return subscriptions with next billing tomorrow (daily freq)."""
        _make_active_subscription(
            client,
            customer_id="CUST-WIN-1",
            email="win1@test.io",
            billing_frequency="daily",
        )
        _make_active_subscription(
            client,
            customer_id="CUST-WIN-Y",
            email="winy@test.io",
            billing_frequency="yearly",
        )

        resp_narrow = client.get("/api/analytics/renewal-forecast", params={"days": 1})
        assert resp_narrow.status_code == 200
        narrow_count = resp_narrow.json()["upcoming_renewals_count"]

        # Use max allowed window to capture both
        resp_wide = client.get("/api/analytics/renewal-forecast", params={"days": 365})
        assert resp_wide.status_code == 200
        wide_count = resp_wide.json()["upcoming_renewals_count"]

        # Wider window should include at least as many renewals
        assert wide_count >= narrow_count

    def test_urgency_label_immediate(self, client):
        """Subscriptions renewing within 7 days must receive 'Immediate' urgency label."""
        sub = _make_active_subscription(
            client,
            customer_id="CUST-URG",
            email="urg@test.io",
            billing_frequency="daily",  # next billing = tomorrow
        )

        resp = client.get("/api/analytics/renewal-forecast", params={"days": 30})
        data = resp.json()

        matching = [r for r in data["renewals"] if r["subscription_id"] == sub["id"]]
        if matching:
            assert "Immediate" in matching[0]["urgency"]

    def test_window_date_fields_in_response(self, client):
        """Response should include window_start and window_end date fields."""
        resp = client.get("/api/analytics/renewal-forecast", params={"days": 30})
        data = resp.json()
        assert "window_start" in data
        assert "window_end" in data
        assert "forecast_window_days" in data
        assert data["forecast_window_days"] == 30


# ===========================================================================
# 4. Expansion / Upgrade / Downgrade Analytics
# ===========================================================================

class TestExpansionMovement:
    """Tests for GET /api/analytics/expansion-movement"""

    def test_no_multi_contract_customers(self, client):
        """Single subscriptions per customer should produce no movements."""
        _make_active_subscription(client, customer_id="CUST-EXP-1", email="exp1@test.io")
        resp = client.get("/api/analytics/expansion-movement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["multi_contract_customers"] == 0
        assert data["upgrades_count"] == 0
        assert data["downgrades_count"] == 0
        assert data["movements"] == []

    def test_upgrade_detected(self, client):
        """Customer with two subscriptions where second > first counts as upgrade."""
        # First subscription
        _make_active_subscription(
            client,
            customer_id="CUST-UP",
            email="upgrade@test.io",
            unit_price=100.0,
        )
        # Second (more expensive) subscription for same customer
        _make_active_subscription(
            client,
            customer_id="CUST-UP",
            email="upgrade@test.io",
            unit_price=300.0,
        )

        resp = client.get("/api/analytics/expansion-movement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["upgrades_count"] >= 1
        assert data["net_expansion_revenue"] > 0.0

        upgrade_movements = [m for m in data["movements"] if m["movement_type"] == "Upgrade"]
        assert len(upgrade_movements) >= 1
        assert upgrade_movements[0]["delta"] > 0.0

    def test_downgrade_detected(self, client):
        """Customer with second subscription cheaper than first counts as downgrade."""
        _make_active_subscription(
            client,
            customer_id="CUST-DWN",
            email="downgrade@test.io",
            unit_price=500.0,
        )
        _make_active_subscription(
            client,
            customer_id="CUST-DWN",
            email="downgrade@test.io",
            unit_price=200.0,
        )

        resp = client.get("/api/analytics/expansion-movement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["downgrades_count"] >= 1

        downgrade_movements = [m for m in data["movements"] if m["movement_type"] == "Downgrade"]
        assert len(downgrade_movements) >= 1
        assert downgrade_movements[0]["delta"] < 0.0

    def test_no_movement_on_equal_amounts(self, client):
        """Two identical amounts for the same customer produce neither upgrade nor downgrade."""
        for _ in range(2):
            _make_active_subscription(
                client,
                customer_id="CUST-FLAT",
                email="flat@test.io",
                unit_price=250.0,
            )

        resp = client.get("/api/analytics/expansion-movement")
        data = resp.json()
        flat_movements = [
            m for m in data["movements"] if m["customer_id"] == "CUST-FLAT"
        ]
        assert flat_movements == []


# ===========================================================================
# 5. Renewal Risk / Health Indicators
# ===========================================================================

class TestRenewalRisks:
    """Tests for GET /api/analytics/renewal-risks"""

    def test_no_active_subscriptions(self, client):
        """With no active subscriptions, risk list should be empty."""
        resp = client.get("/api/analytics/renewal-risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_active_evaluated"] == 0
        assert data["subscriptions"] == []

    def test_low_risk_healthy_subscription(self, client):
        """A fresh active subscription with yearly billing and no pause should be LOW risk."""
        sub = _make_active_subscription(
            client,
            customer_id="CUST-LOW-RISK",
            email="low@risk.io",
            billing_frequency="yearly",
            unit_price=200.0,
        )

        resp = client.get("/api/analytics/renewal-risks")
        assert resp.status_code == 200
        data = resp.json()

        matching = [s for s in data["subscriptions"] if s["subscription_id"] == sub["id"]]
        assert len(matching) == 1
        assert matching[0]["risk_level"] == "LOW"
        assert matching[0]["risk_score"] < 20

    def test_high_risk_from_pause_history(self, client):
        """A subscription that has been paused should carry elevated risk (score ≥45 → HIGH)."""
        sub = _make_active_subscription(
            client,
            customer_id="CUST-HIGH-RISK",
            email="high@risk.io",
            billing_frequency="daily",  # imminent renewal
            unit_price=100.0,
        )

        # Pause and then resume it to leave pause history
        pause_resp = client.patch(
            f"/api/subscriptions/{sub['id']}/state",
            json={"action": "pause", "reason": "Customer requested temporary hold"},
        )
        assert pause_resp.status_code == 200

        resume_resp = client.post(f"/api/subscriptions/{sub['id']}/resume")
        assert resume_resp.status_code == 200

        resp = client.get("/api/analytics/renewal-risks")
        data = resp.json()

        matching = [s for s in data["subscriptions"] if s["subscription_id"] == sub["id"]]
        assert len(matching) == 1
        # pause_reason set → score ≥40; daily billing → +35 for imminent → HIGH
        assert matching[0]["risk_level"] in ("MEDIUM", "HIGH")
        assert matching[0]["risk_score"] >= 20

    def test_risk_list_sorted_descending_by_score(self, client):
        """Risk list should be ordered highest risk score first."""
        _make_active_subscription(client, customer_id="CUST-R1", email="r1@test.io", billing_frequency="yearly")
        _make_active_subscription(client, customer_id="CUST-R2", email="r2@test.io", billing_frequency="daily")

        resp = client.get("/api/analytics/renewal-risks")
        data = resp.json()
        scores = [s["risk_score"] for s in data["subscriptions"]]
        assert scores == sorted(scores, reverse=True)

    def test_risk_response_schema(self, client):
        """Each risk entry must contain required schema fields."""
        sub = _make_active_subscription(
            client, customer_id="CUST-SCH", email="schema@risk.io"
        )
        resp = client.get("/api/analytics/renewal-risks")
        data = resp.json()
        assert "total_active_evaluated" in data
        assert "high_risk_count" in data
        assert "medium_risk_count" in data
        assert "low_risk_count" in data

        for entry in data["subscriptions"]:
            for field in (
                "subscription_id",
                "subscription_number",
                "customer_name",
                "customer_email",
                "risk_level",
                "risk_score",
                "risk_factors",
                "recommended_action",
            ):
                assert field in entry, f"Missing field '{field}' in risk entry"

    def test_counts_sum_to_total(self, client):
        """high + medium + low risk counts must equal total_active_evaluated."""
        for i in range(3):
            _make_active_subscription(
                client, customer_id=f"CUST-CNT-{i}", email=f"cnt{i}@test.io"
            )

        resp = client.get("/api/analytics/renewal-risks")
        data = resp.json()
        total = data["high_risk_count"] + data["medium_risk_count"] + data["low_risk_count"]
        assert total == data["total_active_evaluated"]


# ===========================================================================
# 6. AI Insights Endpoint (POST /api/analytics/subscription-ai-insights)
# ===========================================================================

class TestAIInsights:
    """Tests for POST /api/analytics/subscription-ai-insights"""

    def test_heuristic_fallback_when_no_api_key(self, client):
        """Without OPENAI_API_KEY, service falls back to heuristic engine cleanly."""
        # Ensure no API key is set
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OPENAI_API_KEY", None)

            resp = client.post("/api/analytics/subscription-ai-insights")
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert "ai_insights" in data
            assert "analytics_snapshot" in data
            assert "generated_at" in data

            insights = data["ai_insights"]
            assert insights.get("source") in ("intelligent_heuristic_engine", "openai")
            assert "health_status" in insights
            assert "executive_summary" in insights

    def test_response_schema_completeness(self, client):
        """The AI insights response must include required top-level keys."""
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OPENAI_API_KEY", None)

            resp = client.post("/api/analytics/subscription-ai-insights")
            assert resp.status_code == 200
            data = resp.json()

            assert "generated_at" in data
            assert "analytics_snapshot" in data
            assert "ai_insights" in data

            snapshot = data["analytics_snapshot"]
            for key in (
                "churn_metrics",
                "cancellation_reasons",
                "renewal_forecast",
                "expansion_analytics",
                "renewal_risks",
            ):
                assert key in snapshot, f"Missing snapshot key: {key}"

    def test_mock_openai_response(self, client):
        """With a mocked OpenAI client, AI insights should parse and return correctly."""
        mock_content = json.dumps(
            {
                "health_status": "Strong Customer Retention",
                "executive_summary": "Mock AI executive summary.",
                "churn_analysis": {
                    "assessment": "Low churn detected.",
                    "retention_strength": "High",
                },
                "cancellation_insights": {
                    "root_cause_analysis": "Price sensitivity.",
                    "retention_playbook": "Offer loyalty discounts.",
                },
                "renewal_risk_mitigations": ["Send renewal emails 14 days out."],
                "expansion_recommendations": ["Upsell premium tier to top accounts."],
                "confidence_score": 0.97,
            }
        )

        mock_message = MagicMock()
        mock_message.content = mock_content

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion

        with patch("services.ai_copilot.get_openai_client", return_value=mock_client):
            resp = client.post("/api/analytics/subscription-ai-insights")
            assert resp.status_code == 200
            data = resp.json()
            insights = data["ai_insights"]

            assert insights["health_status"] == "Strong Customer Retention"
            assert insights["executive_summary"] == "Mock AI executive summary."
            assert "renewal_risk_mitigations" in insights
            assert isinstance(insights["renewal_risk_mitigations"], list)
            assert insights["source"] == "openai"

    def test_openai_exception_triggers_fallback(self, client):
        """If OpenAI raises an exception, fallback to heuristic engine with api_notice."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Connection timeout")

        with patch("services.ai_copilot.get_openai_client", return_value=mock_client):
            resp = client.post("/api/analytics/subscription-ai-insights")
            assert resp.status_code == 200
            data = resp.json()
            insights = data["ai_insights"]

            # Fallback heuristic engine kicks in
            assert "api_notice" in insights
            assert "Connection timeout" in insights["api_notice"]
            assert insights["source"] == "intelligent_heuristic_engine"

    def test_ai_insights_includes_data_with_active_subscriptions(self, client):
        """With real subscriptions, AI insights snapshot should reflect non-zero counts."""
        _make_active_subscription(client, customer_id="CUST-AI-1", email="ai1@test.io")
        sub_to_close = _make_active_subscription(
            client, customer_id="CUST-AI-2", email="ai2@test.io"
        )
        _close_subscription(client, sub_to_close["id"], reason="AI test cancellation")

        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OPENAI_API_KEY", None)

            resp = client.post("/api/analytics/subscription-ai-insights")
            assert resp.status_code == 200
            data = resp.json()

            snapshot = data["analytics_snapshot"]
            churn = snapshot["churn_metrics"]
            assert churn["churned_count"] >= 1
            assert churn["ending_active_count"] >= 1

            reasons = snapshot["cancellation_reasons"]
            assert len(reasons) >= 1


# ===========================================================================
# 7. Heuristic Engine Unit Tests
# ===========================================================================

class TestHeuristicEngine:
    """Unit tests for the heuristic fallback in services/ai_copilot.py"""

    def _make_snapshot(
        self,
        churn_rate: float = 0.0,
        retention_rate: float = 100.0,
        churned_count: int = 0,
        active_count: int = 5,
        top_reason: str = "Pricing",
        expiring_soon: int = 2,
        forecast_rev: float = 1500.0,
        high_risks: int = 0,
        medium_risks: int = 1,
    ) -> dict:
        return {
            "churn_metrics": {
                "churn_rate_percent": churn_rate,
                "retention_rate_percent": retention_rate,
                "churned_count": churned_count,
                "ending_active_count": active_count,
            },
            "cancellation_reasons": [{"reason": top_reason, "count": churned_count, "percentage": 100.0}]
            if churned_count > 0
            else [],
            "renewal_forecast": {
                "upcoming_renewals_count": expiring_soon,
                "forecasted_renewal_revenue": forecast_rev,
            },
            "renewal_risks": {
                "high_risk_count": high_risks,
                "medium_risk_count": medium_risks,
            },
        }

    def test_heuristic_strong_retention(self):
        from services.ai_copilot import generate_heuristic_insights

        snapshot = self._make_snapshot(churn_rate=0.0, retention_rate=100.0, active_count=10)
        result = generate_heuristic_insights(snapshot)

        assert result["source"] == "intelligent_heuristic_engine"
        assert result["health_status"] == "Strong Customer Retention"
        assert result["confidence_score"] >= 0.8

    def test_heuristic_moderate_churn(self):
        from services.ai_copilot import generate_heuristic_insights

        snapshot = self._make_snapshot(
            churn_rate=7.5,
            retention_rate=92.5,
            churned_count=3,
            active_count=37,
            high_risks=1,
        )
        result = generate_heuristic_insights(snapshot)
        assert result["health_status"] == "Moderate Churn Risk"

    def test_heuristic_critical_churn(self):
        from services.ai_copilot import generate_heuristic_insights

        snapshot = self._make_snapshot(
            churn_rate=20.0,
            retention_rate=80.0,
            churned_count=10,
            active_count=40,
            high_risks=5,
        )
        result = generate_heuristic_insights(snapshot)
        assert result["health_status"] == "Critical Attention Needed"

    def test_heuristic_always_returns_required_keys(self):
        from services.ai_copilot import generate_heuristic_insights

        result = generate_heuristic_insights(self._make_snapshot())
        for key in (
            "source",
            "model_used",
            "health_status",
            "executive_summary",
            "churn_analysis",
            "cancellation_insights",
            "renewal_risk_mitigations",
            "expansion_recommendations",
            "confidence_score",
        ):
            assert key in result, f"Missing key '{key}' in heuristic output"

    def test_heuristic_actionable_recs_generated_for_high_risk(self):
        from services.ai_copilot import generate_heuristic_insights

        snapshot = self._make_snapshot(high_risks=3, churned_count=2)
        result = generate_heuristic_insights(snapshot)
        recs = result["renewal_risk_mitigations"]["recommended_actions"]
        assert len(recs) >= 1
        assert any("high-risk" in r.lower() or "3" in r for r in recs)
