"""FastAPI router for Product Performance Analytics, Discount Tracking, and AI Insights.
Provides fully typed OpenAPI-documented REST endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import CurrentUser, get_current_user, get_subscription_provider
from .schemas import (
    CatalogOverviewOut,
    ProductPerformanceListOut,
    TopSubscribedOut,
    TopVariantsListOut,
    RevenueComparisonOut,
    DiscountsSummaryOut,
    UnderperformingListOut,
    ProductProfitabilityOut,
    PerformanceTrendsOut,
    AIInsightsOut,
    AIInsightsRequest,
)
from .service_analytics import ProductAnalyticsService
from .service_ai_insights import AIInsightsService

router = APIRouter(prefix="/analytics", tags=["Product Analytics & AI Insights"])


@router.get(
    "/overview",
    response_model=CatalogOverviewOut,
    summary="Get high-level catalog performance overview and health score",
)
def get_catalog_overview(
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Returns aggregated KPIs including total products, active vs inactive counts,
    total units sold, total invoiced & collected revenue, blended margin %,
    active subscriptions, discount counts, and catalog health score.
    """
    return ProductAnalyticsService.get_catalog_overview(db, sub_provider)


@router.get(
    "/performance",
    response_model=ProductPerformanceListOut,
    summary="Comprehensive product performance analytics",
)
def get_product_performance(
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Returns performance metrics for each product in the catalog:
    sales price, cost price, unit margin, margin percentage, active subscribers,
    units sold, total revenue, estimated cost, net profit, ROI %, revenue share,
    profitability tier, and underperforming flags.
    """
    return ProductAnalyticsService.get_product_performance(db, sub_provider)


@router.get(
    "/top-subscribed",
    response_model=TopSubscribedOut,
    summary="Most subscribed products and plans",
)
def get_top_subscribed(
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Returns ranked lists of:
    1. Most subscribed products with subscriber counts and MRR contribution.
    2. Most subscribed subscription plans with billing frequency, MRR & ARR equivalents.
    """
    return ProductAnalyticsService.get_top_subscribed(db, sub_provider)


@router.get(
    "/top-variants",
    response_model=TopVariantsListOut,
    summary="Most popular product variants",
)
def get_top_variants(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Returns ranked product variants by popularity, units sold,
    sales price, cost price, unit margin, and total revenue share.
    """
    return ProductAnalyticsService.get_top_variants(db)


@router.get(
    "/revenue-comparison",
    response_model=RevenueComparisonOut,
    summary="Product and subscription plan revenue comparisons",
)
def get_revenue_comparison(
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Compares revenue contribution across:
    - Products: invoiced revenue, collected revenue, costs, net profit, revenue share %.
    - Plans: pricing, subscribers, MRR, ARR, and portfolio revenue share %.
    """
    return ProductAnalyticsService.get_revenue_comparison(db, sub_provider)


@router.get(
    "/discounts",
    response_model=DiscountsSummaryOut,
    summary="Discount usage analytics, remaining availability, and effectiveness reports",
)
def get_discounts_analytics(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Tracks discount usage:
    - Usage count vs configured usage limit.
    - Remaining availability, exhaustion status, and days until expiry.
    - Discount effectiveness report: total customer savings given vs gross revenue generated.
    - ROI multiplier and effectiveness ratings (High ROI, Healthy, Low ROI, Margin Erosion).
    """
    return ProductAnalyticsService.get_discounts_analytics(db)


@router.get(
    "/underperforming",
    response_model=UnderperformingListOut,
    summary="Identify underperforming products with severity and remedies",
)
def get_underperforming_products(
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Identifies catalog products underperforming due to:
    - Negative profit margins (cost price > sales price)
    - Zero subscribers and zero sales volume
    - Thin profit margins (< 15%)
    - Disproportionately low revenue contribution (< 3%)
    Includes prioritized severity (HIGH, MEDIUM, LOW), root causes, and actionable remedies.
    """
    return ProductAnalyticsService.get_underperforming_products(db, sub_provider)


@router.get(
    "/profitability",
    response_model=ProductProfitabilityOut,
    summary="Product profitability analysis using sales and cost prices",
)
def get_product_profitability(
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Calculates catalog-wide and per-product profitability:
    Unit profit (sales_price - cost_price), gross margin %, total revenue,
    total cost of goods, net profit, and ROI %.
    """
    return ProductAnalyticsService.get_product_profitability(db, sub_provider)


@router.get(
    "/trends",
    response_model=PerformanceTrendsOut,
    summary="Product and plan performance trends over time",
)
def get_performance_trends(
    interval: str = Query("month", pattern="^(month|week)$", description="Aggregation interval"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Time series of revenue, estimated costs, net profit, and subscription trajectory.
    """
    return ProductAnalyticsService.get_performance_trends(db, interval=interval)


@router.post(
    "/ai-insights",
    response_model=AIInsightsOut,
    summary="Generate AI product insights and strategic recommendations",
)
def generate_ai_insights_post(
    request: Optional[AIInsightsRequest] = None,
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Generates intelligent AI product insights analyzing margins, top drivers,
    underperforming products, discount ROI, and prioritized strategic recommendations.
    Uses OpenAI (when configured) or the built-in heuristic analysis engine.
    """
    return AIInsightsService.generate_insights(db, sub_provider, request=request)


@router.get(
    "/ai-insights",
    response_model=AIInsightsOut,
    summary="Fetch current AI-generated product insights (GET shortcut)",
)
def get_ai_insights(
    focus_area: Optional[str] = Query(None, description="Optional focus area: pricing, discounts, retention"),
    db: Session = Depends(get_db),
    sub_provider = Depends(get_subscription_provider),
    user: CurrentUser = Depends(get_current_user),
):
    req = AIInsightsRequest(focus_area=focus_area) if focus_area else None
    return AIInsightsService.generate_insights(db, sub_provider, request=req)


@router.get(
    "/openapi-spec",
    summary="Machine-readable OpenAPI integration guide for AI agents and Copilots",
)
def get_openapi_guide():
    """
    Returns metadata explaining how external AI agents, OpenAPI clients,
    or Copilots can consume these product analytics endpoints.
    """
    return {
        "title": "BrightLoop Product Analytics OpenAPI Interface",
        "description": "Standardized OpenAPI 3.0 endpoints replacing manual copilot queries with direct REST automation.",
        "documentation_url": "/docs#/Product%20Analytics%20%26%20AI%20Insights",
        "openapi_json_url": "/openapi.json",
        "endpoints": [
            {"path": "/api/v1/analytics/overview", "method": "GET", "purpose": "Catalog high-level KPIs"},
            {"path": "/api/v1/analytics/performance", "method": "GET", "purpose": "Per-product margin and revenue"},
            {"path": "/api/v1/analytics/top-subscribed", "method": "GET", "purpose": "Ranked products and plans"},
            {"path": "/api/v1/analytics/top-variants", "method": "GET", "purpose": "Ranked product variants"},
            {"path": "/api/v1/analytics/revenue-comparison", "method": "GET", "purpose": "Cross-product and plan revenue comparisons"},
            {"path": "/api/v1/analytics/discounts", "method": "GET", "purpose": "Discount usage & effectiveness report"},
            {"path": "/api/v1/analytics/underperforming", "method": "GET", "purpose": "Underperforming products & remedies"},
            {"path": "/api/v1/analytics/profitability", "method": "GET", "purpose": "Cost vs sales price profitability"},
            {"path": "/api/v1/analytics/trends", "method": "GET", "purpose": "Time series performance trends"},
            {"path": "/api/v1/analytics/ai-insights", "method": "POST", "purpose": "Generate AI strategic insights"},
        ],
    }


@router.post(
    "/seed-demo-data",
    summary="Seed realistic demo products, variants, plans, and discounts for analytics preview",
    status_code=status.HTTP_201_CREATED,
)
def seed_demo_data(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    from app.seed_analytics import run_seed
    result = run_seed(db)
    return {"status": "success", "message": "Demo analytics data seeded successfully", "details": result}
