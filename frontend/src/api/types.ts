// Mirrors backend/app/modules/billing/schemas.py

export type InvoiceStatus = "draft" | "confirmed" | "paid" | "cancelled";
export type PaymentMethod = "upi" | "bank_transfer" | "cash" | "card" | "other";
export type PaymentStatus = "posted" | "voided";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface InvoiceLine {
  id: string;
  product_id: string | null;
  subscription_line_id: string | null;
  description: string;
  position: number;
  quantity: number;
  unit_price: number;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  line_total: number;
  meta: Record<string, unknown> | null;
}

export interface Payment {
  id: string;
  payment_reference: string;
  invoice_id: string;
  amount: number;
  method: PaymentMethod;
  status: PaymentStatus;
  paid_at: string;
  notes: string | null;
  recorded_by: string | null;
  voided_at: string | null;
  void_reason: string | null;
  created_at: string;
}

export interface InvoiceSummary {
  id: string;
  invoice_number: string;
  subscription_id: string | null;
  customer_id: string;
  customer_name: string | null;
  status: InvoiceStatus;
  issue_date: string;
  due_date: string;
  period_start: string;
  period_end: string;
  currency: string;
  subtotal: number;
  tax_total: number;
  discount_total: number;
  total_amount: number;
  amount_paid: number;
  outstanding: number;
}

export interface InvoiceDetail extends InvoiceSummary {
  notes: string | null;
  last_emailed_at: string | null;
  created_by: string | null;
  created_at: string;
  confirmed_at: string | null;
  cancelled_at: string | null;
  lines: InvoiceLine[];
  payments: Payment[];
}

export interface BillingRun {
  id: string;
  trigger_source: "scheduled" | "manual";
  requested_by: string | null;
  run_for_date: string;
  status: "running" | "success" | "partial" | "failed";
  scanned: number;
  generated: number;
  skipped: number;
  failed: number;
  errors: { subscription_id?: string; message: string }[] | null;
  started_at: string;
  finished_at: string | null;
}

export interface BillingRunResult extends BillingRun {
  remaining: number;
}

export interface DueSubscription {
  subscription_id: string;
  customer_id: string;
  customer_name: string | null;
  billing_frequency: string;
  next_billing_date: string;
  expiry_date: string | null;
  line_count: number;
}

export interface RecentPayment {
  id: string;
  payment_reference: string;
  invoice_id: string;
  invoice_number: string;
  amount: number;
  method: PaymentMethod;
  paid_at: string;
}

export interface OverdueInvoice {
  id: string;
  invoice_number: string;
  customer_id: string;
  customer_name: string | null;
  due_date: string;
  total_amount: number;
  amount_paid: number;
  outstanding: number;
  days_overdue: number;
}

export interface DashboardSummary {
  active_subscriptions: number;
  revenue_received: number;
  outstanding_amount: number;
  overdue_count: number;
  overdue_amount: number;
  draft_count: number;
  recent_payments: RecentPayment[];
  top_overdue: OverdueInvoice[];
}

export interface TrendPoint {
  period: string;
  invoiced: number;
  collected: number;
  outstanding: number;
}

export interface RevenueTrend {
  interval: string;
  points: TrendPoint[];
}

export interface EmailResult {
  sent: boolean;
  emailed_at: string | null;
  reason: string | null;
}

// ── Phase 2 (P4): finance intelligence ─────────────────────────────────────
// Mirrors backend/app/modules/finance_intelligence/schemas.py

export interface MrrPlanRow {
  plan: string;
  mrr: number;
}

export interface MrrFrequencyRow {
  frequency: string;
  mrr: number;
}

export interface MrrSnapshot {
  as_of: string;
  subscription_count: number;
  mrr: number;
  arr: number;
  by_plan: MrrPlanRow[];
  by_frequency: MrrFrequencyRow[];
}

export interface MrrTrendPoint {
  period: string;
  as_of: string;
  mrr: number;
  arr: number;
}

export interface MrrTrend {
  points: MrrTrendPoint[];
}

export interface DateRange {
  from: string;
  to: string;
}

export interface RevenueTrendPoint {
  period: string;
  invoiced: number;
  collected: number;
}

export interface RevenueTrends {
  interval: string;
  range: DateRange;
  previous_range: DateRange;
  totals: { invoiced: number; collected: number };
  previous_totals: { invoiced: number; collected: number };
  growth_pct: { invoiced: number | null; collected: number | null };
  points: RevenueTrendPoint[];
}

export interface BreakdownRow {
  key: string;
  amount: number;
  share_pct: number;
}

export interface Breakdown {
  by: string;
  range: DateRange;
  rows: BreakdownRow[];
}

export interface UpcomingBilling {
  subscription_id: string;
  subscription_number: string;
  customer_id: string;
  next_billing_date: string;
  billing_frequency: string;
  expected_amount: number;
}

export interface DueReceivable {
  invoice_id: string;
  invoice_number: string;
  customer_id: string;
  customer_name: string | null;
  due_date: string;
  outstanding: number;
  days_overdue: number;
}

export interface Forecast {
  as_of: string;
  horizon_days: number;
  horizon_end: string;
  collection_rate: number;
  collection_rate_window_days: number;
  expected_billings: number;
  expected_billings_count: number;
  outstanding_due: number;
  expected_collections: number;
  expected_total_cash_in: number;
  upcoming_billings: UpcomingBilling[];
  due_receivables: DueReceivable[];
}

export type RiskSeverity = "high" | "medium" | "low";
export type RiskCategory =
  | "high_value_overdue"
  | "multiple_overdue"
  | "repeated_late_payments"
  | "renewal_unpaid"
  | "large_exposure";

export interface RiskRecord {
  risk_index: number;
  customer_id: string | null;
  customer_name: string | null;
  subscription_id: string | null;
  invoice_id: string | null;
  invoice_number: string | null;
  outstanding_amount: number;
  days_overdue: number;
  risk_category: string;
  severity: string;
  detection_reason: string;
  recommended_action: string;
}

export interface RiskSummary {
  total_risks: number;
  customers_at_risk: number;
  total_outstanding_at_risk: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
}

export interface RiskList {
  as_of: string;
  summary: RiskSummary;
  risks: RiskRecord[];
}

export interface RiskExplanation {
  explanation: string;
  provider: string;
  model: string | null;
  risk: RiskRecord;
}

export interface CopilotAnswer {
  answer: string;
  intent: string;
  provider: string;
  model: string | null;
  metrics: Record<string, unknown>;
  sources: string[];
  range: Record<string, unknown>;
}

export interface FinancialSummary {
  id: string;
  period_kind: string;
  period_start: string;
  period_end: string;
  metrics: Record<string, unknown>;
  summary_text: string;
  provider: string;
  model: string | null;
  generated_by: string | null;
  created_at: string;
}

// --- Product Performance Analytics & AI Insights -----------------------------

export interface CatalogOverview {
  total_products: number;
  active_products: number;
  inactive_products: number;
  total_variants: number;
  total_plans: number;
  total_units_sold: number;
  total_invoiced_revenue: number;
  total_collected_revenue: number;
  total_estimated_cost: number;
  total_net_profit: number;
  blended_profit_margin_pct: number;
  active_subscriptions_count: number;
  total_discounts_count: number;
  active_discounts_count: number;
  catalog_health_score: number;
  health_grade: string;
}

export interface ProductPerformanceItem {
  product_id: number;
  product_name: string;
  product_type: string;
  sales_price: number;
  cost_price: number;
  unit_margin: number;
  margin_pct: number;
  active_subscribers: number;
  total_units_sold: number;
  total_revenue: number;
  total_cost: number;
  net_profit: number;
  roi_pct: number;
  revenue_share_pct: number;
  profitability_tier: string;
  status: string;
  is_underperforming: boolean;
  underperforming_reasons: string[];
}

export interface ProductPerformanceList {
  total_products: number;
  items: ProductPerformanceItem[];
}

export interface TopSubscribedProduct {
  rank: number;
  product_id: number;
  product_name: string;
  product_type: string;
  sales_price: number;
  active_subscribers: number;
  total_units_sold: number;
  mrr_contribution: number;
  total_revenue: number;
}

export interface TopSubscribedPlan {
  rank: number;
  plan_id: string;
  plan_name: string;
  product_id: number;
  product_name: string;
  billing_frequency: string;
  price: number;
  active_subscribers: number;
  mrr_equivalent: number;
  arr_equivalent: number;
  total_revenue: number;
  status: string;
}

export interface TopSubscribedResponse {
  products: TopSubscribedProduct[];
  plans: TopSubscribedPlan[];
}

export interface TopVariantItem {
  rank: number;
  variant_id: number;
  variant_name: string;
  sku: string | null;
  product_id: number;
  product_name: string;
  sales_price: number;
  cost_price: number;
  unit_margin: number;
  margin_pct: number;
  active_subscribers: number;
  units_sold: number;
  total_revenue: number;
  revenue_share_pct: number;
  is_active: boolean;
}

export interface TopVariantsList {
  total_variants: number;
  items: TopVariantItem[];
}

export interface ProductRevenueComparisonItem {
  product_id: number;
  product_name: string;
  invoiced_revenue: number;
  collected_revenue: number;
  total_cost: number;
  net_profit: number;
  revenue_share_pct: number;
  profit_margin_pct: number;
}

export interface PlanRevenueComparisonItem {
  plan_id: string;
  plan_name: string;
  product_name: string;
  billing_frequency: string;
  price: number;
  active_subscribers: number;
  mrr_equivalent: number;
  arr_equivalent: number;
  total_revenue: number;
  revenue_share_pct: number;
}

export interface RevenueComparisonResponse {
  products: ProductRevenueComparisonItem[];
  plans: PlanRevenueComparisonItem[];
}

export interface DiscountUsageItem {
  discount_id: string;
  name: string;
  code: string;
  discount_type: "percentage" | "fixed_amount" | string;
  discount_value: number;
  usage_count: number;
  usage_limit: number | null;
  remaining_uses: number | null;
  usage_pct: number | null;
  is_exhausted: boolean;
  min_purchase_amount: number;
  is_active: boolean;
  start_date: string;
  expiry_date: string | null;
  is_expired: boolean;
  days_remaining: number | null;
  availability_status: string;
  total_discount_amount_given: number;
  revenue_generated_with_discount: number;
  effectiveness_ratio: number;
  effectiveness_rating: string;
}

export interface DiscountsSummaryResponse {
  total_discounts: number;
  active_discounts: number;
  total_redemptions: number;
  total_savings_given: number;
  total_revenue_from_discounted_orders: number;
  overall_roi_multiplier: number;
  items: DiscountUsageItem[];
}

export interface UnderperformingProductItem {
  product_id: number;
  product_name: string;
  product_type: string;
  sales_price: number;
  cost_price: number;
  unit_margin: number;
  margin_pct: number;
  active_subscribers: number;
  total_units_sold: number;
  total_revenue: number;
  severity: "HIGH" | "MEDIUM" | "LOW";
  issues: string[];
  recommendations: string[];
}

export interface UnderperformingListResponse {
  total_underperforming: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
  items: UnderperformingProductItem[];
}

export interface ProductProfitabilityItem {
  product_id: number;
  product_name: string;
  product_type: string;
  sales_price: number;
  cost_price: number;
  unit_profit: number;
  margin_pct: number;
  units_sold: number;
  total_revenue: number;
  total_cost: number;
  net_profit: number;
  roi_pct: number;
  profitability_tier: string;
}

export interface ProductProfitabilityResponse {
  total_catalog_revenue: number;
  total_catalog_cost: number;
  total_catalog_profit: number;
  catalog_margin_pct: number;
  items: ProductProfitabilityItem[];
}

export interface PerformanceTrendPoint {
  period: string;
  total_revenue: number;
  total_cost: number;
  net_profit: number;
  new_subscriptions: number;
  active_subscriptions: number;
}

export interface PerformanceTrendsResponse {
  interval: string;
  points: PerformanceTrendPoint[];
}

export interface AIInsightsRecommendation {
  id: string;
  priority: "critical" | "high" | "medium" | "low";
  category: "pricing" | "catalog" | "discount" | "growth";
  title: string;
  description: string;
  expected_impact: string;
}

export interface AIInsightsResponse {
  catalog_health_score: number;
  health_grade: string;
  executive_summary: string;
  top_performers_summary: string;
  underperforming_warnings: string[];
  discount_effectiveness_analysis: string;
  actionable_recommendations: AIInsightsRecommendation[];
  generated_by: string;
  generated_at: string;
}
