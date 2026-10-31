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
