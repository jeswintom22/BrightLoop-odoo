import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, qs } from "../../api/client";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { PageHeader, StatCard, TableSkeleton } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { formatMoney } from "../../lib/utils";

interface Totals {
  invoice_count: number;
  invoiced: string;
  collected: string;
  outstanding: string;
  overdue_count: number;
  overdue_amount: string;
}
interface PerformanceReport {
  range: { from: string; to: string };
  previous_range: { from: string; to: string };
  current: Totals;
  previous: Totals;
  growth_pct: { invoiced: string | null; collected: string | null };
  collection_rate: string | null;
  mrr: string;
  arr: string;
  active_subscriptions_in_mrr: number;
  plan_revenue: { key: string; amount: string; share_pct: string }[];
}

const n = (v: string | null | undefined) => Number(v ?? 0);
const trend = (v: string | null) =>
  v == null ? "—" : `${n(v) >= 0 ? "+" : ""}${n(v).toFixed(1)}%`;

export default function ReportsPage() {
  const today = new Date();
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const [from, setFrom] = useState(first.toISOString().slice(0, 10));
  const [to, setTo] = useState(today.toISOString().slice(0, 10));

  const report = useQuery({
    queryKey: ["performance-report", from, to],
    queryFn: () =>
      api<PerformanceReport>(`/finance-intelligence/reports/performance${qs({ from, to })}`),
    retry: 1,
  });

  const r = report.data;

  return (
    <div>
      <PageHeader title="Financial Reports" description="Period performance vs the previous period." />
      <Card className="mb-6">
        <CardContent className="flex flex-wrap items-end gap-4 pt-5">
          <div className="space-y-1"><Label>From</Label><Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
          <div className="space-y-1"><Label>To</Label><Input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></div>
        </CardContent>
      </Card>

      {report.isLoading && <TableSkeleton />}
      {report.isError && (
        <Card><CardContent className="py-8 text-center text-sm text-ink-muted">Report unavailable — check the finance-intelligence service.</CardContent></Card>
      )}
      {r && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Revenue collected" value={formatMoney(n(r.current.collected))} sub={`${trend(r.growth_pct.collected)} vs previous`} />
            <StatCard label="Invoiced" value={formatMoney(n(r.current.invoiced))} sub={`${r.current.invoice_count} invoices · ${trend(r.growth_pct.invoiced)}`} />
            <StatCard label="Outstanding" value={formatMoney(n(r.current.outstanding))} sub={`${r.current.overdue_count} overdue · ${formatMoney(n(r.current.overdue_amount))}`} />
            <StatCard label="Collection rate" value={r.collection_rate == null ? "—" : `${(n(r.collection_rate) * 100).toFixed(1)}%`} sub={`MRR ${formatMoney(n(r.mrr))} · ARR ${formatMoney(n(r.arr))}`} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Period comparison</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <THead><TR><TH>Metric</TH><TH className="text-right">Current</TH><TH className="text-right">Previous</TH></TR></THead>
                  <TBody>
                    <TR><TD>Invoiced</TD><TD className="text-right">{formatMoney(n(r.current.invoiced))}</TD><TD className="text-right text-ink-muted">{formatMoney(n(r.previous.invoiced))}</TD></TR>
                    <TR><TD>Collected</TD><TD className="text-right">{formatMoney(n(r.current.collected))}</TD><TD className="text-right text-ink-muted">{formatMoney(n(r.previous.collected))}</TD></TR>
                    <TR><TD>Invoices issued</TD><TD className="text-right">{r.current.invoice_count}</TD><TD className="text-right text-ink-muted">{r.previous.invoice_count}</TD></TR>
                    <TR><TD>Overdue invoices</TD><TD className="text-right">{r.current.overdue_count}</TD><TD className="text-right text-ink-muted">{r.previous.overdue_count}</TD></TR>
                  </TBody>
                </Table>
                <p className="mt-3 text-xs text-ink-muted">
                  Previous period: {r.previous_range.from} → {r.previous_range.to}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Plan revenue breakdown</CardTitle></CardHeader>
              <CardContent>
                {r.plan_revenue.length === 0 ? (
                  <p className="text-sm text-ink-muted">No plan revenue in this period.</p>
                ) : (
                  <Table>
                    <THead><TR><TH>Plan</TH><TH className="text-right">Revenue</TH><TH className="text-right">Share</TH></TR></THead>
                    <TBody>
                      {r.plan_revenue.map((p) => (
                        <TR key={p.key}>
                          <TD>{p.key}</TD>
                          <TD className="text-right">{formatMoney(n(p.amount))}</TD>
                          <TD className="text-right">{n(p.share_pct).toFixed(1)}%</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
