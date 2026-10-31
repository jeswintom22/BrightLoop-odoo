"""AI explanations for deterministic risk records.

Detection happens in analytics/risk_detection.py (no LLM). This module only
turns a structured risk record into plain language. On any provider failure
the deterministic template is returned — the feature never depends on the
network.
"""

import json
import logging
from decimal import Decimal

from . import prompts
from .provider import LLMError, LLMProvider

logger = logging.getLogger("brightloop.finance_ai")


class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _template_explanation(risk: dict) -> str:
    """Grounded fallback assembled only from the record's own fields."""
    name = risk.get("customer_name") or str(risk.get("customer_id"))
    amount = risk.get("outstanding_amount")
    amount_s = f"₹{Decimal(str(amount)):,.2f}" if amount is not None else "an unquantified amount"
    days = risk.get("days_overdue") or 0
    reason = risk.get("detection_reason", "")
    action = risk.get("recommended_action", "")
    overdue_s = f" {days} day(s) overdue." if days else ""
    return (
        f"{name} was flagged under '{risk.get('risk_category')}' with {amount_s} outstanding.{overdue_s} "
        f"{reason} Recommended next step: {action}"
    )


def explain_risk(llm: LLMProvider, risk: dict) -> dict:
    fallback = _template_explanation(risk)
    try:
        result = llm.generate(
            system=prompts.RISK_EXPLAIN_SYSTEM,
            user=prompts.risk_explain_user(json.dumps(risk, cls=_Encoder, default=str)),
            max_tokens=300,
        )
        text, provider, model = result.text, result.provider, result.model
        if provider == "template":
            text = fallback
    except LLMError as exc:
        logger.warning("risk explain LLM failed (%s) — template fallback", exc)
        text, provider, model = fallback, "template-fallback", None
    return {"explanation": text, "provider": provider, "model": model, "risk": risk}
