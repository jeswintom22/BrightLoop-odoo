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
