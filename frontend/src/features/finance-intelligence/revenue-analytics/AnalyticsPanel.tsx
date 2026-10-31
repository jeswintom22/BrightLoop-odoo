import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, qs } from "../../../api/client";
import type {
  Breakdown,
  Forecast,
  MrrSnapshot,
  MrrTrend,
  RevenueTrends,
} from "../../../api/types";
import { Badge } from "../../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import {
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "../../../components/ui/table";
import { formatDate, formatMoney } from "../../../lib/utils";

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-cream0">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{value}</p>
        {hint && <p className="mt-1 text-xs text-cream0">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function GrowthBadge({ pct }: { pct: number | null }) {
  if (pct === null) return <Badge variant="outline">n/a</Badge>;
  const up = pct >= 0;
  return (
    <Badge variant={up ? "success" : "destructive"}>
      {up ? "+" : ""}
      {pct.toFixed(2)}%
    </Badge>
  );
}

function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * 86400_000).toISOString().slice(0, 10);
}
const todayIso = () => new Date().toISOString().slice(0, 10);

const BREAKDOWN_DIMS = [
  { value: "plan", label: "Plan" },
  { value: "product", label: "Product" },
  { value: "customer", label: "Customer" },
  { value: "period", label: "Billing period" },
  { value: "payment_method", label: "Payment method" },
] as const;

export default function AnalyticsPanel() {
  const [from, setFrom] = useState(isoDaysAgo(90));
  const [to, setTo] = useState(todayIso());
  const [interval, setInterval_] = useState("month");
  const [dim, setDim] = useState<string>("plan");
  const [horizon, setHorizon] = useState(30);

  const mrr = useQuery({
    queryKey: ["fi-mrr"],
    queryFn: () => api<MrrSnapshot>("/finance-intelligence/revenue/mrr"),
  });
  const mrrTrend = useQuery({
    queryKey: ["fi-mrr-trend", from, to],
    queryFn: () =>
      api<MrrTrend>(`/finance-intelligence/revenue/mrr-trend${qs({ from, to })}`),
  });
  const trends = useQuery({
    queryKey: ["fi-trends", interval, from, to],
    queryFn: () =>
      api<RevenueTrends>(
        `/finance-intelligence/revenue/trends${qs({ interval, from, to })}`,
      ),
  });
  const breakdown = useQuery({
    queryKey: ["fi-breakdown", dim, from, to],
    queryFn: () =>
      api<Breakdown>(
        `/finance-intelligence/revenue/breakdown${qs({ by: dim, from, to })}`,
      ),
  });
  const forecast = useQuery({
    queryKey: ["fi-forecast", horizon],
    queryFn: () =>
      api<Forecast>(`/finance-intelligence/revenue/forecast${qs({ horizon_days: horizon })}`),
  });

  const snap = mrr.data;
  const t = trends.data;
  const f = forecast.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <Label htmlFor="fi-from">From</Label>
          <Input id="fi-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="fi-to">To</Label>
          <Input id="fi-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>

      {/* MRR / ARR snapshot */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Kpi label="MRR" value={snap ? formatMoney(snap.mrr) : "—"} hint={snap ? `as of ${snap.as_of}` : undefined} />
        <Kpi label="ARR" value={snap ? formatMoney(snap.arr) : "—"} hint="normalized recurring value" />
        <Kpi label="Active subscriptions" value={snap ? String(snap.subscription_count) : "—"} hint="counted in MRR" />
        <Kpi
          label="Collected (range)"
          value={t ? formatMoney(t.totals.collected) : "—"}
          hint={t ? `${t.range.from} → ${t.range.to}` : undefined}
        />
      </div>

      {snap && (snap.by_plan.length > 0 || snap.by_frequency.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>MRR by plan</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <THead><TR><TH>Plan</TH><TH className="text-right">MRR</TH></TR></THead>
                <TBody>
                  {snap.by_plan.map((r) => (
                    <TR key={r.plan}>
                      <TD>{r.plan}</TD>
                      <TD className="text-right font-medium">{formatMoney(r.mrr)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>MRR by billing frequency</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <THead><TR><TH>Frequency</TH><TH className="text-right">MRR</TH></TR></THead>
                <TBody>
                  {snap.by_frequency.map((r) => (
                    <TR key={r.frequency}>
                      <TD className="capitalize">{r.frequency}</TD>
                      <TD className="text-right font-medium">{formatMoney(r.mrr)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* MRR trend */}
      <Card>
        <CardHeader><CardTitle>MRR trend (month-ends)</CardTitle></CardHeader>
        <CardContent>
          {mrrTrend.isLoading && <p className="text-cream0">Loading…</p>}
          {mrrTrend.data && mrrTrend.data.points.length === 0 && (
            <p className="text-cream0">No recurring subscriptions in range.</p>
          )}
          {mrrTrend.data && mrrTrend.data.points.length > 0 && (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={mrrTrend.data.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="period" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip formatter={(v: number) => formatMoney(v)} />
                <Legend />
                <Line type="monotone" dataKey="mrr" name="MRR" stroke="#0f172a" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="arr" name="ARR" stroke="#64748b" strokeWidth={1} strokeDasharray="4 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Revenue trends: invoiced vs collected */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Revenue trend — invoiced vs collected</CardTitle>
            <select
              className="rounded-md border border-line px-2 py-1 text-sm"
              value={interval}
              onChange={(e) => setInterval_(e.target.value)}
            >
              <option value="day">Daily</option>
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
              <option value="year">Yearly</option>
            </select>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {t && (
            <div className="flex flex-wrap gap-6 text-sm">
              <span>
                Invoiced <strong>{formatMoney(t.totals.invoiced)}</strong>{" "}
                <GrowthBadge pct={t.growth_pct.invoiced} />
              </span>
              <span>
                Collected <strong>{formatMoney(t.totals.collected)}</strong>{" "}
                <GrowthBadge pct={t.growth_pct.collected} />
              </span>
              <span className="text-cream0">
                vs {t.previous_range.from} → {t.previous_range.to} (
                {formatMoney(t.previous_totals.invoiced)} invoiced /{" "}
                {formatMoney(t.previous_totals.collected)} collected)
              </span>
            </div>
          )}
          {trends.isLoading && <p className="text-cream0">Loading…</p>}
          {t && t.points.length > 0 && (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={t.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="period" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip formatter={(v: number) => formatMoney(v)} />
                <Legend />
                <Line type="monotone" dataKey="invoiced" name="Invoiced" stroke="#94a3b8" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="collected" name="Collected" stroke="#0f172a" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
          {t && t.points.length === 0 && (
            <p className="text-cream0">No invoiced or collected revenue in range.</p>
          )}
        </CardContent>
      </Card>

      {/* Breakdown */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Revenue breakdown</CardTitle>
            <select
              className="rounded-md border border-line px-2 py-1 text-sm"
              value={dim}
              onChange={(e) => setDim(e.target.value)}
            >
              {BREAKDOWN_DIMS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {breakdown.isLoading && <p className="text-cream0">Loading…</p>}
          {breakdown.data && breakdown.data.rows.length === 0 && (
            <p className="text-cream0">No data for this dimension in range.</p>
          )}
          {breakdown.data && breakdown.data.rows.length > 0 && (
            <Table>
              <THead>
                <TR>
                  <TH>{BREAKDOWN_DIMS.find((d) => d.value === dim)?.label}</TH>
                  <TH className="text-right">Amount</TH>
                  <TH className="text-right">Share</TH>
                </TR>
              </THead>
              <TBody>
                {breakdown.data.rows.map((r) => (
                  <TR key={r.key}>
                    <TD>{r.key}</TD>
                    <TD className="text-right font-medium">{formatMoney(r.amount)}</TD>
                    <TD className="text-right text-cream0">{r.share_pct.toFixed(1)}%</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
          {dim === "payment_method" && (
            <p className="mt-2 text-xs text-cream0">
              Payment-method breakdown reflects cash collected (posted payments);
              other dimensions reflect invoiced revenue.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Forecast */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Collection forecast (deterministic)</CardTitle>
            <select
              className="rounded-md border border-line px-2 py-1 text-sm"
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
            >
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
            </select>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {forecast.isLoading && <p className="text-cream0">Loading…</p>}
          {f && (
            <>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <Kpi label="Expected billings" value={formatMoney(f.expected_billings)} hint={`${f.expected_billings_count} subscription cycle(s)`} />
                <Kpi label="Receivables due" value={formatMoney(f.outstanding_due)} hint="existing confirmed invoices" />
                <Kpi label="Expected collections" value={formatMoney(f.expected_collections)} hint={`at ${(f.collection_rate * 100).toFixed(1)}% realized rate`} />
                <Kpi label="Expected cash-in" value={formatMoney(f.expected_total_cash_in)} hint="collections + billings × rate" />
              </div>
              <p className="text-xs text-cream0">
                Transparent heuristic — not an ML prediction. Collection rate is the
                realized rate over the trailing {f.collection_rate_window_days} days.
              </p>
              {f.upcoming_billings.length > 0 && (
                <Table>
                  <THead>
                    <TR><TH>Subscription</TH><TH>Bills on</TH><TH>Frequency</TH><TH className="text-right">Expected</TH></TR>
                  </THead>
                  <TBody>
                    {f.upcoming_billings.map((b) => (
                      <TR key={b.subscription_id}>
                        <TD>{b.subscription_number}</TD>
                        <TD>{formatDate(b.next_billing_date)}</TD>
                        <TD className="capitalize">{b.billing_frequency}</TD>
                        <TD className="text-right font-medium">{formatMoney(b.expected_amount)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
