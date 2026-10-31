import json
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except ImportError:  # openai is optional; heuristic fallback still works
    OpenAI = None  # type: ignore[assignment]


def get_openai_client() -> Optional["OpenAI"]:
    """Retrieves OpenAI client if API key is present in environment."""
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def generate_heuristic_insights(analytics_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent heuristic rules-engine fallback when OpenAI API key is unavailable.
    Provides structured, actionable analysis of churn, cancellation causes, and renewal risks.
    """
    churn_metrics = analytics_data.get("churn_metrics", {})
    churn_rate = churn_metrics.get("churn_rate_percent", 0.0)
    retention_rate = churn_metrics.get("retention_rate_percent", 100.0)
    churned_count = churn_metrics.get("churned_count", 0)
    active_count = churn_metrics.get("ending_active_count", 0)

    reasons = analytics_data.get("cancellation_reasons", [])
    top_reason = reasons[0]["reason"] if reasons else "None recorded"

    renewal = analytics_data.get("renewal_forecast", {})
    expiring_soon = renewal.get("upcoming_renewals_count", 0)
    forecast_rev = renewal.get("forecasted_renewal_revenue", 0.0)

    risks = analytics_data.get("renewal_risks", {})
    high_risks = risks.get("high_risk_count", 0)
    medium_risks = risks.get("medium_risk_count", 0)

    # Determine health posture
    if churn_rate > 15.0 or high_risks > 3:
        health_status = "Critical Attention Needed"
        summary = (
            f"Subscription churn rate is elevated at {churn_rate:.1f}% with {churned_count} cancellations. "
            f"There are {high_risks} high-risk accounts requiring urgent CSM intervention."
        )
    elif churn_rate > 5.0 or high_risks > 0:
        health_status = "Moderate Churn Risk"
        summary = (
            f"Healthy base of {active_count} active subscriptions with {retention_rate:.1f}% retention. "
            f"{high_risks} accounts exhibit churn signals and should be contacted before expiry."
        )
    else:
        health_status = "Strong Customer Retention"
        summary = (
            f"Outstanding retention performance at {retention_rate:.1f}%. "
            f"Low cancellation volume with {expiring_soon} upcoming renewals representing ${forecast_rev:,.2f} in pipeline."
        )

    actionable_recs = []
    if high_risks > 0:
        actionable_recs.append(
            f"Deploy targeted check-ins for the {high_risks} high-risk subscribers identified with pause history or imminent expiry."
        )
    if reasons:
        actionable_recs.append(
            f"Address root cause for top cancellation driver ('{top_reason}') via onboarding reviews and value demonstration."
        )
    actionable_recs.append(
        f"Automate renewal reminders 14 and 7 days prior to next billing date for {expiring_soon} upcoming renewal contracts."
    )

    return {
        "source": "intelligent_heuristic_engine",
        "model_used": "rules-engine-v1",
        "health_status": health_status,
        "executive_summary": summary,
        "churn_analysis": {
            "churn_rate_percent": churn_rate,
            "retention_rate_percent": retention_rate,
            "active_base": active_count,
            "churned_in_period": churned_count,
            "status_assessment": (
                "Churn is within healthy SaaS benchmark (<5%)"
                if churn_rate <= 5.0
                else "Churn is above standard SaaS target (>5%)"
            ),
        },
        "cancellation_insights": {
            "primary_driver": top_reason,
            "distribution": reasons[:5],
            "recommendation": "Conduct exit interviews on paused/closed accounts to gather product feedback.",
        },
        "renewal_risk_mitigations": {
            "high_risk_count": high_risks,
            "medium_risk_count": medium_risks,
            "recommended_actions": actionable_recs,
        },
        "expansion_recommendations": [
            "Identify top 20% active accounts with consistent yearly renewals for tiered enterprise add-ons.",
            "Offer multi-seat annual discounts to accounts nearing monthly renewal milestones.",
        ],
        "confidence_score": 0.92,
    }


def generate_subscription_insights(analytics_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formats subscription metrics into an LLM prompt and requests comprehensive AI analysis
    using the official OpenAI SDK. Falls back cleanly to the heuristic engine if unavailable.
    """
    client = get_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not client:
        return generate_heuristic_insights(analytics_data)

    system_prompt = (
        "You are the AI Subscription & Revenue Intelligence Copilot for BrightLoop. "
        "Analyze the provided subscription lifecycle metrics, churn rate, cancellation reasons, "
        "and renewal risk flags. Return a strict JSON response containing actionable insights, "
        "executive summary, risk mitigations, and expansion opportunities."
    )

    user_prompt = f"""
Analyze the following BrightLoop subscription analytics snapshot:
{json.dumps(analytics_data, indent=2, default=str)}

Respond in valid JSON with these exact keys:
{{
  "health_status": "string",
  "executive_summary": "string",
  "churn_analysis": {{
    "assessment": "string",
    "retention_strength": "string"
  }},
  "cancellation_insights": {{
    "root_cause_analysis": "string",
    "retention_playbook": "string"
  }},
  "renewal_risk_mitigations": [
    "string"
  ],
  "expansion_recommendations": [
    "string"
  ],
  "confidence_score": 0.95
}}
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=800,
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        parsed["source"] = "openai"
        parsed["model_used"] = model
        return parsed
    except Exception as e:
        # Fallback cleanly on error
        fallback = generate_heuristic_insights(analytics_data)
        fallback["api_notice"] = f"OpenAI call bypassed or failed ({str(e)}), served via heuristic copilot."
        return fallback
