"""AI Product Insights Service.
Supports OpenAI API (when OPENAI_API_KEY is configured) and provides a rich,
data-driven heuristic intelligence engine fallback for 100% out-of-the-box operation.
"""

import datetime as dt
from decimal import Decimal
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import utc_now
from .schemas import AIInsightsOut, AIInsightsRecommendation, AIInsightsRequest
from .service_analytics import ProductAnalyticsService

logger = logging.getLogger("brightloop.analytics.ai")
settings = get_settings()


class AIInsightsService:
    @classmethod
    def generate_insights(
        cls,
        session: Session,
        subscription_provider: Any = None,
        request: Optional[AIInsightsRequest] = None,
    ) -> AIInsightsOut:
        # Gather live analytics data
        overview = ProductAnalyticsService.get_catalog_overview(session, subscription_provider)
        perf = ProductAnalyticsService.get_product_performance(session, subscription_provider)
        underperforming = ProductAnalyticsService.get_underperforming_products(session, subscription_provider)
        discounts = ProductAnalyticsService.get_discounts_analytics(session)

        # Check if OpenAI is enabled and configured
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
            try:
                ai_out = cls._call_openai_insights(
                    overview=overview,
                    perf=perf,
                    underperforming=underperforming,
                    discounts=discounts,
                    request=request,
                )
                if ai_out:
                    return ai_out
            except Exception as e:
                logger.warning("OpenAI insights call failed, falling back to local AI engine: %s", str(e))

        # Built-in Heuristic AI Generation Engine
        return cls._generate_heuristic_insights(
            overview=overview,
            perf=perf,
            underperforming=underperforming,
            discounts=discounts,
            request=request,
        )

    @classmethod
    def _call_openai_insights(
        cls,
        overview: Any,
        perf: Any,
        underperforming: Any,
        discounts: Any,
        request: Optional[AIInsightsRequest],
    ) -> Optional[AIInsightsOut]:
        prompt_data = {
            "catalog_overview": overview.model_dump(),
            "top_products": [p.model_dump() for p in perf.items[:5]],
            "underperforming_products": [u.model_dump() for u in underperforming.items],
            "discounts_summary": discounts.model_dump(exclude={"items"}),
            "discount_items": [d.model_dump() for d in discounts.items[:5]],
            "focus_area": request.focus_area if request else None,
        }

        system_prompt = (
            "You are the Chief Product & Financial Intelligence Copilot for BrightLoop. "
            "Analyze the subscription catalog, product margins, discounts, and underperforming products. "
            "Respond ONLY with a valid JSON object matching the exact schema:\n"
            "{\n"
            '  "catalog_health_score": <int 0-100>,\n'
            '  "health_grade": <"A+"|"A"|"B"|"C"|"D">,\n'
            '  "executive_summary": "<concise 2-3 sentence financial & catalog assessment>",\n'
            '  "top_performers_summary": "<paragraph highlighting star products & revenue drivers>",\n'
            '  "underperforming_warnings": ["<warning 1>", "<warning 2>", ...],\n'
            '  "discount_effectiveness_analysis": "<analysis of discount ROI, cannibalization, or exhaustion>",\n'
            '  "actionable_recommendations": [\n'
            '    {\n'
            '      "id": "rec-1",\n'
            '      "priority": "critical"|"high"|"medium"|"low",\n'
            '      "category": "pricing"|"catalog"|"discount"|"growth",\n'
            '      "title": "<title>",\n'
            '      "description": "<concrete action with specific numbers>",\n'
            '      "expected_impact": "<e.g. +18% gross margin or ₹45,000 ARR>"\n'
            '    }\n'
            "  ]\n"
            "}"
        )

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions"

        payload = {
            "model": settings.OPENAI_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this data:\n{json.dumps(prompt_data)}"},
            ],
            "temperature": 0.4,
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                recs = [
                    AIInsightsRecommendation(
                        id=r.get("id", f"rec-{i}"),
                        priority=r.get("priority", "medium"),
                        category=r.get("category", "growth"),
                        title=r.get("title", ""),
                        description=r.get("description", ""),
                        expected_impact=r.get("expected_impact", ""),
                    )
                    for i, r in enumerate(parsed.get("actionable_recommendations", []), start=1)
                ]

                return AIInsightsOut(
                    catalog_health_score=int(parsed.get("catalog_health_score", overview.catalog_health_score)),
                    health_grade=str(parsed.get("health_grade", overview.health_grade)),
                    executive_summary=parsed.get("executive_summary", ""),
                    top_performers_summary=parsed.get("top_performers_summary", ""),
                    underperforming_warnings=parsed.get("underperforming_warnings", []),
                    discount_effectiveness_analysis=parsed.get("discount_effectiveness_analysis", ""),
                    actionable_recommendations=recs,
                    generated_by=f"OpenAI {settings.OPENAI_MODEL}",
                    generated_at=utc_now(),
                )

        return None

    @classmethod
    def _generate_heuristic_insights(
        cls,
        overview: Any,
        perf: Any,
        underperforming: Any,
        discounts: Any,
        request: Optional[AIInsightsRequest],
    ) -> AIInsightsOut:
        """
        Intelligent rule-based synthesis that evaluates real numbers, margin breaches,
        discount capacity, and underperforming products to deliver rich strategic advice.
        """
        top_product = perf.items[0] if perf.items else None
        worst_margin_product = min(perf.items, key=lambda x: x.margin_pct) if perf.items else None
        high_sev = [u for u in underperforming.items if u.severity == "HIGH"]

        # 1. Executive Summary
        exec_summary = (
            f"The product catalog comprises {overview.total_products} products with {overview.active_products} active "
            f"and generates a blended profit margin of {overview.blended_profit_margin_pct}%. Total recognized revenue stands "
            f"at ₹{overview.total_invoiced_revenue:,.2f} against estimated delivery costs of ₹{overview.total_estimated_cost:,.2f}. "
        )
        if high_sev:
            exec_summary += (
                f"Urgent action required on {len(high_sev)} high-severity underperforming product(s) "
                f"exhibiting negative unit margins or zero adoption."
            )
        else:
            exec_summary += "Overall catalog margin profile is healthy, with balanced subscription adoption across core tiers."

        # 2. Top Performers Summary
        if top_product:
            top_perf_text = (
                f"'{top_product.product_name}' is the leading revenue anchor, accounting for "
                f"{top_product.revenue_share_pct}% of catalog revenue (₹{top_product.total_revenue:,.2f}) with "
                f"a strong {top_product.margin_pct}% gross margin and {top_product.active_subscribers} active subscribers. "
                f"Tiered plans associated with this product provide consistent recurring cashflow."
            )
        else:
            top_perf_text = "Catalog does not yet have established sales records."

        # 3. Underperforming Warnings
        warnings = []
        for u in underperforming.items[:4]:
            if u.cost_price >= u.sales_price:
                warnings.append(
                    f"CRITICAL: '{u.product_name}' operates at a unit loss of ₹{(u.cost_price - u.sales_price):,.2f} "
                    f"(Cost ₹{u.cost_price:,.2f} vs Sales ₹{u.sales_price:,.2f}). Immediate repricing required."
                )
            elif u.active_subscribers == 0:
                warnings.append(
                    f"STAGNANT: '{u.product_name}' has 0 active subscribers despite active catalog status. Review viability."
                )
            elif u.margin_pct < 15.0:
                warnings.append(
                    f"LOW MARGIN: '{u.product_name}' yields only {u.margin_pct}% margin, below the 15% sustainability benchmark."
                )

        if not warnings:
            warnings.append("No critical product anomalies detected. All active products meet baseline margin criteria.")

        # 4. Discount Effectiveness Analysis
        exhausted_count = sum(1 for d in discounts.items if d.is_exhausted)
        near_cap_count = sum(1 for d in discounts.items if d.availability_status == "Near Capacity")
        disc_analysis = (
            f"Discounts have generated ₹{discounts.total_revenue_from_discounted_orders:,.2f} in gross revenue from "
            f"₹{discounts.total_savings_given:,.2f} in customer concessions, demonstrating a {discounts.overall_roi_multiplier}x "
            f"gross revenue ROI multiplier. "
        )
        if exhausted_count > 0:
            disc_analysis += f"{exhausted_count} discount code(s) have reached 100% capacity and are no longer redeemable. "
        if near_cap_count > 0:
            disc_analysis += f"{near_cap_count} code(s) are near maximum redemption capacity (>80% used)."

        # 5. Strategic Recommendations
        recommendations: List[AIInsightsRecommendation] = []
        rec_idx = 1

        # Recommendation 1: Fix negative margin products
        for u in high_sev:
            if u.cost_price >= u.sales_price:
                rec_price = (u.cost_price * Decimal("1.35")).quantize(Decimal("1.00"))
                recommendations.append(
                    AIInsightsRecommendation(
                        id=f"rec-{rec_idx}",
                        priority="critical",
                        category="pricing",
                        title=f"Reprice '{u.product_name}' to Eliminate Loss",
                        description=(
                            f"Increase sales price from ₹{u.sales_price:,.2f} to ₹{rec_price:,.2f} "
                            f"to establish a 26% gross profit margin over unit cost of ₹{u.cost_price:,.2f}."
                        ),
                        expected_impact=f"+₹{(rec_price - u.sales_price):,.2f} margin per subscriber",
                    )
                )
                rec_idx += 1

        # Recommendation 2: Bundle zero-subscriber products
        zero_subs = [u for u in underperforming.items if u.active_subscribers == 0]
        if zero_subs and top_product:
            target_p = zero_subs[0]
            recommendations.append(
                AIInsightsRecommendation(
                    id=f"rec-{rec_idx}",
                    priority="high",
                    category="catalog",
                    title=f"Cross-Bundle '{target_p.product_name}' with Top Seller",
                    description=(
                        f"Attach '{target_p.product_name}' as an optional 14-day add-on module "
                        f"to '{top_product.product_name}' to ignite initial adoption without custom acquisition spend."
                    ),
                    expected_impact="Initial subscriber base of 15-25 accounts within 30 days",
                )
            )
            rec_idx += 1

        # Recommendation 3: Replenish or adjust top discounts
        near_or_exhausted = [d for d in discounts.items if d.is_exhausted or d.availability_status == "Near Capacity"]
        if near_or_exhausted:
            d_target = near_or_exhausted[0]
            recommendations.append(
                AIInsightsRecommendation(
                    id=f"rec-{rec_idx}",
                    priority="medium",
                    category="discount",
                    title=f"Adjust Cap for High-Performing Code '{d_target.code}'",
                    description=(
                        f"Code '{d_target.code}' has used {d_target.usage_count}/{d_target.usage_limit or 'unlimited'} redemptions "
                        f"at an impressive {d_target.effectiveness_ratio}x ROI. Expand limit by 50 slots to capture ongoing conversion momentum."
                    ),
                    expected_impact=f"Estimated +₹{(d_target.revenue_generated_with_discount * Decimal('0.3')):,.2f} in incremental revenue",
                )
            )
            rec_idx += 1

        # Recommendation 4: Growth optimization
        recommendations.append(
            AIInsightsRecommendation(
                id=f"rec-{rec_idx}",
                priority="low",
                category="growth",
                title="Annual Plan Upsell Incentive",
                description=(
                    "Implement a 15% discount incentive for monthly subscribers switching to annual billing to lock in "
                    "upfront cash collection and reduce recurring churn."
                ),
                expected_impact="+22% increase in immediate cash collection",
            )
        )

        return AIInsightsOut(
            catalog_health_score=overview.catalog_health_score,
            health_grade=overview.health_grade,
            executive_summary=exec_summary,
            top_performers_summary=top_perf_text,
            underperforming_warnings=warnings,
            discount_effectiveness_analysis=disc_analysis,
            actionable_recommendations=recommendations,
            generated_by="BrightLoop Analytics AI Engine (Heuristic)",
            generated_at=utc_now(),
        )
