from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...deps import get_db, require_roles
from ..auth.models import Customer
from .models import Quotation, Subscription
from .services.ai_copilot import generate_subscription_insights

router = APIRouter(
    prefix="/analytics",
    tags=["Subscription Intelligence & Analytics"],
    dependencies=[Depends(require_roles("admin", "staff"))],
)


def _subscription_total(sub: Subscription) -> float:
    return sum(float(i.quantity) * float(i.unit_price) for i in sub.items)


def _customer_map(db: Session) -> Dict[Any, Customer]:
    return {c.id: c for c in db.query(Customer).all()}


def _effective_end(sub: Subscription) -> Optional[date]:
    return sub.expiry_date or sub.next_billing_date


@router.get(
    "/churn-retention",
    summary="Calculate subscription churn and customer retention rates over a date window",
)
def get_churn_and_retention(
    start_date: Optional[date] = Query(None, description="Start date of period (defaults to 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date of period (defaults to today)"),
    db: Session = Depends(get_db),
):
    """
    Computes cohort churn rate and customer retention rate over the specified date window.

    Note: the schema has no closed_at timestamp, so a closed subscription's
    updated_at is used as the approximation for when it closed.
    """
    today = date.today()
    period_end = end_date or today
    period_start = start_date or (period_end - timedelta(days=30))

    period_start_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    period_end_dt = datetime.combine(period_end, datetime.max.time(), tzinfo=timezone.utc)

    # 1. Active at start of period
    starting_active = (
        db.query(Subscription)
        .filter(
            Subscription.start_date <= period_start,
            (Subscription.status != "closed") | (Subscription.updated_at > period_start_dt),
        )
        .count()
    )

    # 2. Newly acquired during period
    new_subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.start_date >= period_start,
            Subscription.start_date <= period_end,
        )
        .count()
    )

    # 3. Churned / closed during period
    churned_subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.status == "closed",
            Subscription.updated_at >= period_start_dt,
            Subscription.updated_at <= period_end_dt,
        )
        .all()
    )
    churned_count = len(churned_subscriptions)
    churned_revenue = sum(_subscription_total(s) for s in churned_subscriptions)

    # 4. Currently active ending count
    ending_active = db.query(Subscription).filter(Subscription.status == "active").count()

    cohort_base = starting_active + new_subscriptions
    if cohort_base > 0:
        churn_rate = round((churned_count / cohort_base) * 100.0, 2)
    elif starting_active > 0:
        churn_rate = round((churned_count / starting_active) * 100.0, 2)
    else:
        churn_rate = 0.0

    retention_rate = round(max(0.0, 100.0 - churn_rate), 2)

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "starting_active_count": starting_active,
        "newly_acquired_count": new_subscriptions,
        "churned_count": churned_count,
        "churned_revenue_loss": round(churned_revenue, 2),
        "ending_active_count": ending_active,
        "churn_rate_percent": churn_rate,
        "retention_rate_percent": retention_rate,
        "cohort_health": (
            "Excellent (<5% churn)"
            if churn_rate < 5.0
            else ("Moderate (5-10% churn)" if churn_rate <= 10.0 else "High Churn Alert (>10%)")
        ),
    }


@router.get(
    "/cancellation-reasons",
    summary="Track and aggregate subscription cancellation causes",
)
def get_cancellation_reasons(db: Session = Depends(get_db)):
    """
    Returns breakdown and distribution of reasons for churned/closed subscriptions.

    Note: the schema does not currently store a close reason on Subscription, so
    every closure reports as unspecified until such a field is added.
    """
    closed_subs = db.query(Subscription).filter(Subscription.status == "closed").all()
    total_closed = len(closed_subs)

    reason_counts: Dict[str, int] = {}
    for sub in closed_subs:
        raw_reason = (getattr(sub, "close_reason", None) or "").strip()
        reason = raw_reason if raw_reason else "Unspecified / Voluntary Exit"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
    breakdown = [
        {
            "reason": reason,
            "count": count,
            "percentage": round((count / total_closed * 100.0), 1) if total_closed > 0 else 0.0,
        }
        for reason, count in sorted_reasons
    ]

    return {
        "total_cancellations": total_closed,
        "breakdown": breakdown,
        "primary_cancellation_driver": breakdown[0]["reason"] if breakdown else "None recorded",
    }


@router.get(
    "/renewal-forecast",
    summary="Renewal forecasting and upcoming contract expiry tracking",
)
def get_renewal_forecast(
    days: int = Query(30, ge=1, le=365, description="Lookahead window in days (default 30)"),
    db: Session = Depends(get_db),
):
    """
    Identifies subscriptions expiring or up for renewal within the specified timeframe
    and calculates expected renewal revenue.
    """
    today = date.today()
    horizon = today + timedelta(days=days)

    active_subs = db.query(Subscription).filter(Subscription.status == "active").all()
    customers = _customer_map(db)
    currency = get_settings().DEFAULT_CURRENCY

    upcoming = []
    total_forecast_revenue = 0.0

    for sub in active_subs:
        effective_date = _effective_end(sub)
        if effective_date and today <= effective_date <= horizon:
            amt = _subscription_total(sub)
            total_forecast_revenue += amt
            days_left = (effective_date - today).days
            customer = customers.get(sub.customer_id)
            upcoming.append(
                {
                    "subscription_id": str(sub.id),
                    "subscription_number": sub.subscription_number,
                    "customer_id": str(sub.customer_id),
                    "customer_name": customer.name if customer else None,
                    "customer_email": customer.email if customer else None,
                    "renewal_date": effective_date.isoformat(),
                    "days_until_renewal": days_left,
                    "amount": amt,
                    "currency": currency,
                    "billing_frequency": sub.billing_frequency,
                    "urgency": "Immediate (<=7d)" if days_left <= 7 else "Upcoming",
                }
            )

    upcoming.sort(key=lambda x: x["days_until_renewal"])

    return {
        "forecast_window_days": days,
        "window_start": today.isoformat(),
        "window_end": horizon.isoformat(),
        "upcoming_renewals_count": len(upcoming),
        "forecasted_renewal_revenue": round(total_forecast_revenue, 2),
        "currency": currency,
        "renewals": upcoming,
    }


@router.get(
    "/expansion-movement",
    summary="Track subscription upgrades, downgrades, and net expansion movements",
)
def get_expansion_analytics(db: Session = Depends(get_db)):
    """
    Analyzes multi-order customers to quantify account expansion, upgrades, and contraction.
    """
    all_subs = db.query(Subscription).order_by(Subscription.created_at.asc()).all()
    customers = _customer_map(db)

    customer_subs: Dict[Any, List[Subscription]] = {}
    for sub in all_subs:
        customer_subs.setdefault(sub.customer_id, []).append(sub)

    upgrades = 0
    downgrades = 0
    expansion_amount = 0.0
    movements = []

    for cust_id, subs in customer_subs.items():
        if len(subs) >= 2:
            prev = subs[-2]
            curr = subs[-1]
            prev_total = _subscription_total(prev)
            curr_total = _subscription_total(curr)
            diff = curr_total - prev_total
            expansion_amount += diff
            customer = customers.get(curr.customer_id)
            if diff > 0:
                upgrades += 1
                movements.append({
                    "customer_id": str(cust_id),
                    "customer_name": customer.name if customer else None,
                    "movement_type": "Upgrade",
                    "previous_amount": prev_total,
                    "new_amount": curr_total,
                    "delta": round(diff, 2),
                })
            elif diff < 0:
                downgrades += 1
                movements.append({
                    "customer_id": str(cust_id),
                    "customer_name": customer.name if customer else None,
                    "movement_type": "Downgrade",
                    "previous_amount": prev_total,
                    "new_amount": curr_total,
                    "delta": round(diff, 2),
                })

    return {
        "multi_contract_customers": len([c for c, s in customer_subs.items() if len(s) >= 2]),
        "upgrades_count": upgrades,
        "downgrades_count": downgrades,
        "net_expansion_revenue": round(expansion_amount, 2),
        "movements": movements,
    }


@router.get(
    "/renewal-risks",
    summary="Health indicators and churn risk flags for active subscriptions",
)
def get_renewal_risks(db: Session = Depends(get_db)):
    """
    Scores each active subscription for renewal/churn risk based on pause state,
    expiry proximity, and pricing anomalies.
    """
    today = date.today()
    active_subs = (
        db.query(Subscription)
        .filter(Subscription.status.in_(["active", "paused"]))
        .all()
    )
    customers = _customer_map(db)
    quotations = {q.id: q for q in db.query(Quotation).all()}

    risk_list = []
    high_count = 0
    medium_count = 0
    low_count = 0

    for sub in active_subs:
        score = 0
        factors = []

        if sub.status == "paused":
            score += 40
            factors.append("Account is currently paused")

        effective_date = _effective_end(sub)
        if effective_date:
            days_left = (effective_date - today).days
            if days_left <= 7:
                score += 35
                factors.append(f"Expires in {days_left} days without renewal confirmed")
            elif days_left <= 30:
                score += 20
                factors.append(f"Renewal upcoming in {days_left} days")

        quotation = quotations.get(sub.quotation_id)
        heavy_discount = (
            quotation is not None
            and float(quotation.subtotal or 0) > 0
            and float(quotation.discount_total or 0) / float(quotation.subtotal) >= 0.25
        )
        if heavy_discount:
            score += 15
            factors.append("Subscribed under heavy promotional discount (>=25%)")

        if not effective_date:
            score += 10
            factors.append("No next billing or expiration date recorded")

        if score >= 45:
            level = "HIGH"
            high_count += 1
            action = "Urgent: CSM call required within 24 hours to present renewal incentive."
        elif score >= 20:
            level = "MEDIUM"
            medium_count += 1
            action = "Moderate: Dispatch automated value review and renewal notification email."
        else:
            level = "LOW"
            low_count += 1
            action = "Healthy: Standard recurring billing cycle."

        customer = customers.get(sub.customer_id)
        risk_list.append(
            {
                "subscription_id": str(sub.id),
                "subscription_number": sub.subscription_number,
                "customer_name": customer.name if customer else None,
                "customer_email": customer.email if customer else None,
                "risk_level": level,
                "risk_score": min(score, 100),
                "risk_factors": factors if factors else ["Healthy usage and billing schedule"],
                "recommended_action": action,
            }
        )

    risk_list.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "total_active_evaluated": len(active_subs),
        "high_risk_count": high_count,
        "medium_risk_count": medium_count,
        "low_risk_count": low_count,
        "subscriptions": risk_list,
    }


@router.post(
    "/subscription-ai-insights",
    summary="Generate AI-powered subscription intelligence and renewal risk insights",
)
def get_ai_insights(db: Session = Depends(get_db)):
    """
    Compiles real-time churn metrics, cancellation trends, and renewal risk flags,
    then generates strategic AI recommendations via OpenAI gpt-4o-mini (with intelligent heuristic fallback).
    """
    churn_metrics = get_churn_and_retention(db=db)
    reasons = get_cancellation_reasons(db=db)
    renewal = get_renewal_forecast(days=30, db=db)
    expansion = get_expansion_analytics(db=db)
    risks = get_renewal_risks(db=db)

    analytics_snapshot = {
        "churn_metrics": churn_metrics,
        "cancellation_reasons": reasons["breakdown"],
        "renewal_forecast": {
            "upcoming_renewals_count": renewal["upcoming_renewals_count"],
            "forecasted_renewal_revenue": renewal["forecasted_renewal_revenue"],
        },
        "expansion_analytics": {
            "upgrades": expansion["upgrades_count"],
            "downgrades": expansion["downgrades_count"],
            "net_expansion": expansion["net_expansion_revenue"],
        },
        "renewal_risks": {
            "high_risk_count": risks["high_risk_count"],
            "medium_risk_count": risks["medium_risk_count"],
            "low_risk_count": risks["low_risk_count"],
            "top_high_risk_accounts": [
                s for s in risks["subscriptions"] if s["risk_level"] == "HIGH"
            ][:5],
        },
    }

    insights = generate_subscription_insights(analytics_snapshot)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics_snapshot": analytics_snapshot,
        "ai_insights": insights,
    }
