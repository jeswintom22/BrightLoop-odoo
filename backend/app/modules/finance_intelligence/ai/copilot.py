"""AI Finance Copilot — deterministic intent → verified metrics → LLM prose.

Flow (per docs/PHASE2_PERSON4_ARCHITECTURE.md):
1. classify(question) — keyword rules, no LLM. Unknown → capability list.
2. resolve period — "this month", "last month", "this quarter" …
3. run the mapped analytics function(s) — real DB aggregates only, plus the
   P2/P3 contract providers when the intent needs them.
4. hand metrics JSON to the LLM for wording; the provider layer degrades to
   the template path (still grounded — templates embed the same numbers).

The LLM never sees the database and never calculates.
"""

import datetime as dt
import json
import logging
import re
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ....core.time import business_date
from ...billing.models import Invoice, Payment
from ..analytics import forecasting, mrr_arr, revenue, risk_detection
from ..contracts import ProductAnalyticsProvider, SubscriptionAnalyticsProvider
from . import prompts
from .provider import LLMError, LLMProvider

logger = logging.getLogger("brightloop.finance_ai")

CENTS = Decimal("0.01")
MAX_QUESTION_LEN = 1000


class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (dt.date, dt.datetime)):
            return o.isoformat()
        return super().default(o)


def _j(obj) -> str:
    return json.dumps(obj, cls=_Encoder, default=str)


# --- period resolution ---------------------------------------------------------


def _month_bounds(y: int, m: int) -> tuple[dt.date, dt.date]:
    start = dt.date(y, m, 1)
    end = (dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)) - dt.timedelta(days=1)
    return start, end


def _quarter_bounds(y: int, q: int) -> tuple[dt.date, dt.date]:
    start = dt.date(y, (q - 1) * 3 + 1, 1)
    end = dt.date(y + (1 if q == 4 else 0), 1 if q == 4 else q * 3 + 1, 1) - dt.timedelta(days=1)
    return start, end


def resolve_period(question: str) -> tuple[dt.date, dt.date, str]:
    """Relative-period phrases → concrete dates. Default: current month."""
    q = question.lower()
    today = business_date()
    if "last month" in q or "previous month" in q:
        first = dt.date(today.year, today.month, 1)
        prev_end = first - dt.timedelta(days=1)
        return *_month_bounds(prev_end.year, prev_end.month), "last month"
    if "last quarter" in q or "previous quarter" in q:
        cur_q = (today.month - 1) // 3 + 1
        y, qn = (today.year - 1, 4) if cur_q == 1 else (today.year, cur_q - 1)
        return *_quarter_bounds(y, qn), "last quarter"
    if "this quarter" in q:
        return *_quarter_bounds(today.year, (today.month - 1) // 3 + 1), "this quarter"
    if "last year" in q:
        return dt.date(today.year - 1, 1, 1), dt.date(today.year - 1, 12, 31), "last year"
    if "this year" in q or "year to date" in q or "ytd" in q:
        return dt.date(today.year, 1, 1), today, "this year"
    if "today" in q:
        return today, today, "today"
    m = re.search(r"last (\d+) days", q)
    if m:
        days = min(int(m.group(1)), 365)
        return today - dt.timedelta(days=days - 1), today, f"last {days} days"
    return *_month_bounds(today.year, today.month), "this month"


# --- intent classification -----------------------------------------------------

_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("revenue_growth", ("compared", "growth", "decrease", "increase", "decline", "grew", "why did revenue", "changed compared", "trend")),
    ("forecast", ("forecast", "expected collection", "upcoming collection", "expected cash")),
    ("risks", ("risk", "prioritize", "priority", "at risk", "biggest financial")),
    ("mrr", ("mrr", "monthly recurring")),
    ("arr", ("arr", "annual recurring")),
    ("renewals", ("renewal", "renew", "due for renewal", "expiring")),
    ("top_products_margin", ("profitable", "profitability", "margin")),
    ("top_products", ("products generate", "which products", "top products", "best-selling", "best selling")),
    ("top_plans", ("plans generate", "which plans", "which subscription plans", "underperforming", "plan performance", "most recurring revenue")),
    ("recurring_revenue", ("recurring revenue", "recurring")),
    ("top_debtors", ("highest outstanding", "top debtors", "most outstanding", "owe the most", "who owes")),
    ("outstanding", ("outstanding", "still owed", "unpaid", "owed to us", "receivable")),
    ("overdue", ("overdue", "past due", "late invoice")),
    ("active_subscriptions", ("active subscription", "how many subscription", "subscription count")),
    ("churn", ("churn", "retention", "cancelled subscription", "attrition")),
    ("payments_recent", ("payments received", "payments this month", "recent payments", "show me payments")),
    ("revenue_invoiced", ("invoiced", "billed")),
    ("revenue_collected", ("revenue", "collected", "how much did we make", "earn")),
]

# Order matters — first match wins (more specific intents above).


def classify(question: str) -> str:
    q = question.lower()
    for intent, keywords in _RULES:
        if any(k in q for k in keywords):
            return intent
    return "revenue_collected" if "revenue" in q else "unknown"


# --- metric gatherers ------------------------------------------------------------


def _totals(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    lo = dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.timezone.utc)
    hi = dt.datetime.combine(date_to, dt.time.max, tzinfo=dt.timezone.utc)
    invoiced = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Invoice.total_amount), 0)).where(
            Invoice.status.in_(["confirmed", "paid"]),
            Invoice.issue_date >= date_from,
            Invoice.issue_date <= date_to,
        )
    ) or Decimal("0")
    collected = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Payment.amount), 0)).where(
            Payment.status == "posted",
            Payment.paid_at >= lo,
            Payment.paid_at <= hi,
        )
    ) or Decimal("0")
    return {
        "invoiced": Decimal(str(invoiced)).quantize(CENTS),
        "collected": Decimal(str(collected)).quantize(CENTS),
    }


def _gather(
    intent: str,
    session: Session,
    q_from: dt.date,
    q_to: dt.date,
    label: str,
    product_analytics: ProductAnalyticsProvider,
    subscription_analytics: SubscriptionAnalyticsProvider,
) -> tuple[dict, list[str], dict]:
    """Returns (metrics, sources, ranges). Raises nothing — missing
    integrations surface as available=False inside the metrics payload."""
    today = business_date()
    ranges = {"question_period": {"from": q_from.isoformat(), "to": q_to.isoformat(), "label": label}}
    metrics: dict = {}
    sources: list[str] = []

    def add(name: str, data):
        metrics.update(data)
        sources.append(name)

    if intent in ("revenue_collected", "revenue_invoiced"):
        add("revenue.totals", _totals(session, q_from, q_to))
    elif intent == "revenue_growth":
        add("revenue.trends", revenue.revenue_trends(session, interval="month", date_from=q_from, date_to=q_to))
        add("revenue.breakdown.plan", {"by_plan": revenue.breakdown(session, by="plan", date_from=q_from, date_to=q_to)})
    elif intent in ("mrr", "arr", "recurring_revenue", "top_plans"):
        snap = mrr_arr.mrr_snapshot(session, today)
        add("mrr_arr.snapshot", snap)
        if intent == "top_plans":
            try:
                pa = product_analytics.product_analytics(session)
                add(
                    "p2.product_analytics",
                    {
                        "available": pa.available,
                        "note": pa.note,
                        "most_popular_plans": [vars(r) for r in pa.most_popular_plans],
                        "underperforming_plans": [vars(r) for r in pa.underperforming_plans],
                    },
                )
            except Exception as exc:  # contract may be unimplemented upstream
                logger.warning("P2 analytics unavailable: %s", exc)
                add("p2.product_analytics", {"available": False, "note": str(exc)})
    elif intent == "top_products" or intent == "top_products_margin":
        try:
            pa = product_analytics.product_analytics(session)
            add(
                "p2.product_analytics",
                {
                    "available": pa.available,
                    "note": pa.note,
                    "top_products_by_revenue": [vars(r) for r in pa.top_products_by_revenue],
                    "top_products_by_margin": [vars(r) for r in pa.top_products_by_margin],
                },
            )
        except Exception as exc:
            logger.warning("P2 analytics unavailable: %s", exc)
            add("p2.product_analytics", {"available": False, "note": str(exc)})
        add("revenue.breakdown.product", {"by_product": revenue.breakdown(session, by="product", date_from=q_from, date_to=q_to)})
    elif intent == "outstanding":
        outstanding = session.scalar(
            sa.select(
                sa.func.coalesce(sa.func.sum(Invoice.total_amount - Invoice.amount_paid), 0)
            ).where(Invoice.status == "confirmed")
        ) or Decimal("0")
        add("revenue.outstanding", {"outstanding_total": Decimal(str(outstanding)).quantize(CENTS)})
        add("revenue.breakdown.customer", {"top_customers_by_invoiced": revenue.breakdown(session, by="customer", date_from=q_from, date_to=q_to)})
    elif intent == "top_debtors":
        rows = session.execute(
            sa.select(
                Invoice.customer_id,
                sa.func.sum(Invoice.total_amount - Invoice.amount_paid).label("o"),
            )
            .where(Invoice.status == "confirmed")
            .group_by(Invoice.customer_id)
            .order_by(sa.desc("o"))
            .limit(10)
        ).all()
        customers = sa.table("customers", sa.column("id", sa.Uuid), sa.column("name"))
        names = {
            r.id: r.name
            for r in session.execute(
                sa.select(customers).where(customers.c.id.in_([x.customer_id for x in rows] or []))
            ).all()
        }
        add(
            "revenue.top_debtors",
            {
                "debtors": [
                    {
                        "customer_id": str(r.customer_id),
                        "customer_name": names.get(r.customer_id),
                        "outstanding": Decimal(str(r.o)).quantize(CENTS),
                    }
                    for r in rows
                ]
            },
        )
    elif intent == "overdue":
        row = session.execute(
            sa.select(
                sa.func.count(Invoice.id),
                sa.func.coalesce(sa.func.sum(Invoice.total_amount - Invoice.amount_paid), 0),
            ).where(Invoice.status == "confirmed", Invoice.due_date < today)
        ).one()
        add("revenue.overdue", {"overdue_count": int(row[0]), "overdue_amount": Decimal(str(row[1])).quantize(CENTS), "as_of": today.isoformat()})
    elif intent == "active_subscriptions" or intent == "churn" or intent == "renewals":
        try:
            sa_ = subscription_analytics.subscription_analytics(session)
            add(
                "p3.subscription_analytics",
                {
                    "available": sa_.available,
                    "note": sa_.note,
                    "active_count": sa_.active_count,
                    "paused_count": sa_.paused_count,
                    "closed_count": sa_.closed_count,
                    "churned_last_30d": sa_.churned_last_30d,
                    "renewals_due_30d": sa_.renewals_due_30d,
                    "expiring_30d": sa_.expiring_30d,
                    "upcoming_renewals": [vars(r) for r in sa_.upcoming_renewals],
                },
            )
        except Exception as exc:
            logger.warning("P3 analytics unavailable: %s", exc)
            add("p3.subscription_analytics", {"available": False, "note": str(exc)})
        if intent == "renewals":
            add("forecast.upcoming_billings", {"upcoming_billings": forecasting.forecast(session, horizon_days=30)["upcoming_billings"]})
    elif intent == "forecast":
        add("forecast.collections", forecasting.forecast(session, horizon_days=30))
    elif intent == "risks":
        risks = risk_detection.detect_risks(session, as_of=today)
        add("risk.detection", {"summary": risk_detection.risk_summary(risks), "top_risks": risks[:10]})
    elif intent == "payments_recent":
        lo = dt.datetime.combine(q_from, dt.time.min, tzinfo=dt.timezone.utc)
        hi = dt.datetime.combine(q_to, dt.time.max, tzinfo=dt.timezone.utc)
        rows = session.execute(
            sa.select(Payment, Invoice.invoice_number)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(Payment.status == "posted", Payment.paid_at >= lo, Payment.paid_at <= hi)
            .order_by(Payment.paid_at.desc())
            .limit(15)
        ).all()
        add(
            "payments.recent",
            {
                "payments": [
                    {
                        "payment_reference": p.payment_reference,
                        "invoice_number": num,
                        "amount": Decimal(str(p.amount)).quantize(CENTS),
                        "method": p.method,
                        "paid_at": p.paid_at.isoformat(),
                    }
                    for p, num in rows
                ],
                "total": Decimal(str(sum(Decimal(str(p.amount)) for p, _ in rows))).quantize(CENTS),
            },
        )

    return metrics, sources, ranges


# --- template answers (fallback — grounded, never invented) ----------------------


def _money(v) -> str:
    return f"₹{Decimal(str(v)):,.2f}"


def _template_answer(intent: str, metrics: dict, label: str) -> str:
    m = metrics
    if intent == "revenue_collected" or intent == "revenue_invoiced":
        t = m
        return (
            f"For {label}: invoiced {_money(t['invoiced'])}, collected {_money(t['collected'])} "
            f"(from invoices issued and posted payments in that period)."
        )
    if intent == "revenue_growth":
        t = m["totals"]; g = m["growth_pct"]; p = m["previous_totals"]
        prev = m["previous_range"] if "previous_range" in m else {}
        def pct(v):
            return "n/a (previous period was zero)" if v is None else f"{v}%"
        return (
            f"{label}: invoiced {_money(t['invoiced'])} (growth {pct(g['invoiced'])}), "
            f"collected {_money(t['collected'])} (growth {pct(g['collected'])}). "
            f"Previous period {prev.get('from')}–{prev.get('to')}: invoiced {_money(p['invoiced'])}, "
            f"collected {_money(p['collected'])}."
        )
    if intent in ("mrr", "arr", "recurring_revenue"):
        return (
            f"Current MRR is {_money(m['mrr'])} and ARR is {_money(m['arr'])} "
            f"across {m['subscription_count']} active subscription(s), as of {m['as_of']}."
        )
    if intent == "top_plans":
        plans = m.get("by_plan", [])
        top = ", ".join(f"{r['plan']} {_money(r['mrr'])}" for r in plans[:3]) or "no active-plan data"
        return f"MRR is {_money(m['mrr'])} across {m['subscription_count']} active subscription(s). Top plans by MRR: {top}."
    if intent in ("top_products", "top_products_margin"):
        rows = m.get("by_product", [])
        top = ", ".join(f"{r['key']} {_money(r['amount'])}" for r in rows[:3]) or "no product revenue in range"
        return f"Top products by invoiced revenue ({label}): {top}."
    if intent == "outstanding":
        return f"Total outstanding on confirmed invoices is {_money(m['outstanding_total'])}."
    if intent == "top_debtors":
        rows = m.get("debtors", [])
        top = ", ".join(f"{r['customer_name'] or r['customer_id']} {_money(r['outstanding'])}" for r in rows[:5]) or "none"
        return f"Highest outstanding balances: {top}."
    if intent == "overdue":
        return f"{m['overdue_count']} invoice(s) are overdue totalling {_money(m['overdue_amount'])} as of {m['as_of']}."
    if intent in ("active_subscriptions", "churn", "renewals"):
        if not m.get("available", True):
            return f"Subscription analytics are unavailable: {m.get('note', 'unknown error')}."
        base = (
            f"Active {m['active_count']}, paused {m['paused_count']}, closed {m['closed_count']}; "
            f"{m['renewals_due_30d']} renewal(s) and {m['expiring_30d']} expiry(ies) in the next 30 days; "
            f"{m['churned_last_30d']} closed in the last 30 days (approximate — see note)."
        )
        if intent == "renewals":
            upcoming = m.get("upcoming_billings", [])
            top = "; ".join(
                f"{r['subscription_number']} due {r['next_billing_date']} est. {_money(r['expected_amount'])}"
                for r in upcoming[:5]
            )
            return base + (f" Upcoming: {top}." if top else " No upcoming billings in 30 days.")
        return base
    if intent == "forecast":
        return (
            f"Next {m['horizon_days']} days: expected billings {_money(m['expected_billings'])} "
            f"({m['expected_billings_count']} subscription cycles); receivables due {_money(m['outstanding_due'])}; "
            f"expected collections ≈ {_money(m['expected_collections'])} at the trailing-90-day collection rate of "
            f"{m['collection_rate']}."
        )
    if intent == "risks":
        s = m["summary"]
        tops = m.get("top_risks", [])
        top = "; ".join(
            f"{r['customer_name'] or r['customer_id']} — {r['risk_category']} {_money(r['outstanding_amount'])}"
            for r in tops[:3]
        )
        return (
            f"{s['total_risks']} risk(s) across {s['customers_at_risk']} customer(s); "
            f"total outstanding at risk {_money(s['total_outstanding_at_risk'])} "
            f"(high {s['by_severity']['high']}, medium {s['by_severity']['medium']}, low {s['by_severity']['low']})."
            + (f" Top: {top}." if top else "")
        )
    if intent == "payments_recent":
        return f"{len(m['payments'])} posted payment(s) in {label}, total {_money(m['total'])}."
    return (
        "I can answer questions about revenue (collected vs invoiced), MRR/ARR, "
        "outstanding and overdue amounts, top debtors, active subscriptions, "
        "renewals, collection forecasts, product/plan performance and financial "
        "risks. Try: 'How much revenue did we collect this month?'"
    )


# --- orchestration ----------------------------------------------------------------


def answer_question(
    session: Session,
    *,
    question: str,
    llm: LLMProvider,
    product_analytics: ProductAnalyticsProvider,
    subscription_analytics: SubscriptionAnalyticsProvider,
) -> dict:
    question = question.strip()[:MAX_QUESTION_LEN]
    if not question:
        return {
            "answer": "Please ask a finance question.",
            "intent": "unknown",
            "provider": "none",
            "model": None,
            "metrics": {},
            "sources": [],
            "range": {},
        }

    intent = classify(question)
    q_from, q_to, label = resolve_period(question)

    if intent == "unknown":
        return {
            "answer": _template_answer("unknown", {}, label),
            "intent": intent,
            "provider": "none",
            "model": None,
            "metrics": {},
            "sources": [],
            "range": {"question_period": {"from": q_from.isoformat(), "to": q_to.isoformat(), "label": label}},
        }

    metrics, sources, ranges = _gather(
        intent, session, q_from, q_to, label, product_analytics, subscription_analytics
    )

    fallback = _template_answer(intent, metrics, label)
    try:
        result = llm.generate(
            system=prompts.COPILOT_SYSTEM,
            user=prompts.copilot_user(question, _j(metrics), _j(ranges)),
            max_tokens=600,
        )
        answer_text, provider, model = result.text, result.provider, result.model
        if provider == "template":
            answer_text = fallback
    except LLMError as exc:
        logger.warning("LLM call failed (%s) — template fallback", exc)
        answer_text, provider, model = fallback, "template-fallback", None

    return {
        "answer": answer_text,
        "intent": intent,
        "provider": provider,
        "model": model,
        "metrics": metrics,
        "sources": sources,
        "range": ranges,
    }
