"""AI-generated financial summaries from verified report metrics."""

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


def _template_summary(metrics: dict) -> str:
    """Deterministic grounded fallback built from the same metrics JSON."""
    cur = metrics.get("current", {})
    prev = metrics.get("previous", {})
    growth = metrics.get("growth_pct", {})
    rng = metrics.get("range", {})

    def money(key):
        v = cur.get(key)
        return f"₹{Decimal(str(v)):,.2f}" if v is not None else "unavailable"

    def pct(key):
        v = growth.get(key)
        return "n/a (previous period zero)" if v is None else f"{v}%"

    observations = []
    if growth.get("collected") is not None and Decimal(str(growth["collected"])) < 0:
        observations.append("collected revenue declined versus the previous period")
    if growth.get("collected") is not None and Decimal(str(growth["collected"])) > 0:
        observations.append("collected revenue grew versus the previous period")
    overdue = cur.get("overdue_count", 0)
    if overdue:
        observations.append(f"{overdue} invoice(s) remain overdue totalling ₹{Decimal(str(cur.get('overdue_amount', 0))):,.2f}")
    if not observations:
        observations.append("no exceptional movements detected in the period")

    actions = []
    if overdue:
        actions.append("prioritize collection on the overdue invoices listed in the risk report")
    if growth.get("invoiced") is not None and Decimal(str(growth["invoiced"])) < 0:
        actions.append("investigate the decline in invoiced revenue by plan breakdown")
    if not actions:
        actions.append("maintain current collections cadence")

    return (
        f"PERFORMANCE\n"
        f"Period {rng.get('from')} to {rng.get('to')}: invoiced {money('invoiced')} "
        f"across {cur.get('invoice_count', 0)} invoice(s); collected {money('collected')}; "
        f"collection rate {metrics.get('collection_rate')}; MRR {money('mrr')}; ARR {money('arr')}; "
        f"outstanding {money('outstanding')}; overdue {cur.get('overdue_count', 0)} invoice(s) "
        f"worth ₹{Decimal(str(cur.get('overdue_amount', 0))):,.2f}. "
        f"Previous period invoiced ₹{Decimal(str(prev.get('invoiced', 0))):,.2f}, "
        f"collected ₹{Decimal(str(prev.get('collected', 0))):,.2f} "
        f"(growth — invoiced {pct('invoiced')}, collected {pct('collected')}).\n\n"
        f"OBSERVATIONS\n- " + "\n- ".join(observations) + "\n\n"
        f"ACTIONS\n- " + "\n- ".join(actions)
    )


def generate_summary(llm: LLMProvider, metrics: dict) -> dict:
    """Returns {summary_text, provider, model}. Never raises on LLM failure."""
    fallback = _template_summary(metrics)
    try:
        result = llm.generate(
            system=prompts.SUMMARY_SYSTEM,
            user=prompts.summary_user(json.dumps(metrics, cls=_Encoder, default=str)),
            max_tokens=800,
        )
        text, provider, model = result.text, result.provider, result.model
        if provider == "template":
            text = fallback
    except LLMError as exc:
        logger.warning("summary LLM failed (%s) — template fallback", exc)
        text, provider, model = fallback, "template-fallback", None
    return {"summary_text": text, "provider": provider, "model": model}
