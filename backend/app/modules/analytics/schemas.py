"""Pydantic v2 schemas for Product Performance Analytics and AI Insights."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Serialize Decimals as JSON numbers (or floats) for standard API / UI handling
JSONDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v) if v is not None else 0.0, return_type=float, when_used="json"),
]


class CatalogOverviewOut(BaseModel):
    """High-level catalog performance KPIs."""
    total_products: int
    active_products: int
    inactive_products: int
    total_variants: int
    total_plans: int
    total_units_sold: int
    total_invoiced_revenue: JSONDecimal
    total_collected_revenue: JSONDecimal
    total_estimated_cost: JSONDecimal
    total_net_profit: JSONDecimal
    blended_profit_margin_pct: float
    active_subscriptions_count: int
    total_discounts_count: int
    active_discounts_count: int
    catalog_health_score: int
    health_grade: str


class ProductPerformanceItem(BaseModel):
    """Individual product performance record."""
    product_id: int
    product_name: str
    product_type: str
    sales_price: JSONDecimal
    cost_price: JSONDecimal
    unit_margin: JSONDecimal
    margin_pct: float
    active_subscribers: int
    total_units_sold: int
    total_revenue: JSONDecimal
    total_cost: JSONDecimal
    net_profit: JSONDecimal
    roi_pct: float
    revenue_share_pct: float
    profitability_tier: str
    status: str
    is_underperforming: bool
    underperforming_reasons: List[str]


class ProductPerformanceListOut(BaseModel):
    total_products: int
    items: List[ProductPerformanceItem]


class TopSubscribedProductItem(BaseModel):
    """Product ranked by subscription base."""
    rank: int
    product_id: int
    product_name: str
    product_type: str
    sales_price: JSONDecimal
    active_subscribers: int
    total_units_sold: int
    mrr_contribution: JSONDecimal
    total_revenue: JSONDecimal


class TopSubscribedPlanItem(BaseModel):
    """Subscription plan ranked by subscriber count and recurring revenue."""
    rank: int
    plan_id: int
    plan_name: str
    product_id: int
    product_name: str
    billing_frequency: str
    price: JSONDecimal
    active_subscribers: int
    mrr_equivalent: JSONDecimal
    arr_equivalent: JSONDecimal
    total_revenue: JSONDecimal
    status: str


class TopSubscribedOut(BaseModel):
    products: List[TopSubscribedProductItem]
    plans: List[TopSubscribedPlanItem]


class TopVariantItem(BaseModel):
    """Product variant performance."""
    rank: int
    variant_id: int
    variant_name: str
    sku: Optional[str]
    product_id: int
    product_name: str
    sales_price: JSONDecimal
    cost_price: JSONDecimal
    unit_margin: JSONDecimal
    margin_pct: float
    active_subscribers: int
    units_sold: int
    total_revenue: JSONDecimal
    revenue_share_pct: float
    is_active: bool


class TopVariantsListOut(BaseModel):
    total_variants: int
    items: List[TopVariantItem]


class ProductRevenueComparisonItem(BaseModel):
    """Comparison item for products."""
    product_id: int
    product_name: str
    invoiced_revenue: JSONDecimal
    collected_revenue: JSONDecimal
    total_cost: JSONDecimal
    net_profit: JSONDecimal
    revenue_share_pct: float
    profit_margin_pct: float


class PlanRevenueComparisonItem(BaseModel):
    """Comparison item across subscription plans."""
    plan_id: int
    plan_name: str
    product_name: str
    billing_frequency: str
    price: JSONDecimal
    active_subscribers: int
    mrr_equivalent: JSONDecimal
    arr_equivalent: JSONDecimal
    total_revenue: JSONDecimal
    revenue_share_pct: float


class RevenueComparisonOut(BaseModel):
    products: List[ProductRevenueComparisonItem]
    plans: List[PlanRevenueComparisonItem]


class DiscountUsageItem(BaseModel):
    """Detailed discount tracking & effectiveness metrics."""
    discount_id: int
    name: str
    code: str
    discount_type: str  # percentage | fixed_amount
    discount_value: JSONDecimal
    usage_count: int
    usage_limit: Optional[int]
    remaining_uses: Optional[int]
    usage_pct: Optional[float]
    is_exhausted: bool
    min_purchase_amount: JSONDecimal
    is_active: bool
    start_date: dt.datetime
    expiry_date: Optional[dt.datetime]
    is_expired: bool
    days_remaining: Optional[int]
    availability_status: str  # Available | Near Capacity | Exhausted | Expired | Inactive
    total_discount_amount_given: JSONDecimal
    revenue_generated_with_discount: JSONDecimal
    effectiveness_ratio: float  # revenue_generated / total_discount_amount_given
    effectiveness_rating: str  # High ROI | Healthy | Low ROI | Margin Erosion | No Redemptions


class DiscountsSummaryOut(BaseModel):
    total_discounts: int
    active_discounts: int
    total_redemptions: int
    total_savings_given: JSONDecimal
    total_revenue_from_discounted_orders: JSONDecimal
    overall_roi_multiplier: float
    items: List[DiscountUsageItem]


class UnderperformingProductItem(BaseModel):
    """Identified underperforming product with severity and recommendations."""
    product_id: int
    product_name: str
    product_type: str
    sales_price: JSONDecimal
    cost_price: JSONDecimal
    unit_margin: JSONDecimal
    margin_pct: float
    active_subscribers: int
    total_units_sold: int
    total_revenue: JSONDecimal
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    issues: List[str]
    recommendations: List[str]


class UnderperformingListOut(BaseModel):
    total_underperforming: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    items: List[UnderperformingProductItem]


class ProductProfitabilityItem(BaseModel):
    """Product profitability analysis based on sales and cost prices."""
    product_id: int
    product_name: str
    product_type: str
    sales_price: JSONDecimal
    cost_price: JSONDecimal
    unit_profit: JSONDecimal
    margin_pct: float
    units_sold: int
    total_revenue: JSONDecimal
    total_cost: JSONDecimal
    net_profit: JSONDecimal
    roi_pct: float
    profitability_tier: str


class ProductProfitabilityOut(BaseModel):
    total_catalog_revenue: JSONDecimal
    total_catalog_cost: JSONDecimal
    total_catalog_profit: JSONDecimal
    catalog_margin_pct: float
    items: List[ProductProfitabilityItem]


class TrendPointOut(BaseModel):
    period: str
    total_revenue: JSONDecimal
    total_cost: JSONDecimal
    net_profit: JSONDecimal
    new_subscriptions: int
    active_subscriptions: int


class PerformanceTrendsOut(BaseModel):
    interval: str  # month | week
    points: List[TrendPointOut]


class AIInsightsRecommendation(BaseModel):
    id: str
    priority: Literal["critical", "high", "medium", "low"]
    category: Literal["pricing", "catalog", "discount", "growth"]
    title: str
    description: str
    expected_impact: str


class AIInsightsOut(BaseModel):
    catalog_health_score: int
    health_grade: str
    executive_summary: str
    top_performers_summary: str
    underperforming_warnings: List[str]
    discount_effectiveness_analysis: str
    actionable_recommendations: List[AIInsightsRecommendation]
    generated_by: str
    generated_at: dt.datetime


class AIInsightsRequest(BaseModel):
    focus_area: Optional[str] = None  # e.g. "pricing", "discounts", "retention", "margins"
    include_recommendations: bool = True
