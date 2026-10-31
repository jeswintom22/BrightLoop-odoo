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
import { Link } from "react-router-dom";
import { api, qs } from "../../api/client";
import type { DashboardSummary, RevenueTrend } from "../../api/types";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { StatusBadge } from "../../components/ui/badge";
import {
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "../../components/ui/table";
import { formatDate, formatMoney } from "../../lib/utils";

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-cream0">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [interval, setInterval] = useState("month");

  const summary = useQuery({
    queryKey: ["dashboard-summary", from, to],
    queryFn: () =>
      api<DashboardSummary>(`/dashboard/summary${qs({ from, to })}`),
  });
  const trend = useQuery({
    queryKey: ["revenue-trend", interval, from, to],
    queryFn: () =>
      api<RevenueTrend>(
        `/dashboard/revenue-trend${qs({ interval, from, to })}`,
      ),
  });

  const s = summary.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="from">From</Label>
          <Input
            id="from"
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
          <div>
            <Label htmlFor="to">To</Label>
            <Input
              id="to"
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
        </div>
        <Link
          to="/intelligence"
          className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-cream-card hover:bg-ink"
        >
          Revenue intelligence →
        </Link>
      </div>

      {summary.isLoading && <p className="text-cream0">Loading…</p>}
      {summary.isError && (
        <p className="text-danger">Failed to load dashboard.</p>
      )}

      {s && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Kpi label="Active subscriptions" value={String(s.active_subscriptions)} />
          <Kpi label="Revenue received" value={formatMoney(s.revenue_received)} />
          <Kpi label="Outstanding" value={formatMoney(s.outstanding_amount)} />
          <Kpi
            label={`Overdue (${s.overdue_count})`}
            value={formatMoney(s.overdue_amount)}
          />
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Revenue trend</CardTitle>
            <select
              className="rounded-md border border-line px-2 py-1 text-sm"
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
            >
              <option value="day">Daily</option>
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {trend.data && trend.data.points.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trend.data.points}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="invoiced" stroke="#6366f1" />
                <Line type="monotone" dataKey="collected" stroke="#10b981" />
                <Line type="monotone" dataKey="outstanding" stroke="#f59e0b" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-10 text-center text-sm text-cream0">
              No invoicing activity in this range yet.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent payments</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <THead>
                <TR>
                  <TH>Reference</TH>
                  <TH>Invoice</TH>
                  <TH>Method</TH>
                  <TH className="text-right">Amount</TH>
                </TR>
              </THead>
              <TBody>
                {s?.recent_payments.map((p) => (
                  <TR key={p.id}>
                    <TD className="font-mono text-xs">{p.payment_reference}</TD>
                    <TD>
                      <Link
                        className="text-sage-deep hover:underline"
                        to={`/invoices/${p.invoice_id}`}
                      >
                        {p.invoice_number}
                      </Link>
                    </TD>
                    <TD className="capitalize">{p.method.replace("_", " ")}</TD>
                    <TD className="text-right">{formatMoney(p.amount)}</TD>
                  </TR>
                ))}
                {s && s.recent_payments.length === 0 && (
                  <TR>
                    <TD colSpan={4} className="text-center text-cream0">
                      No payments yet.
                    </TD>
                  </TR>
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Overdue invoices</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <THead>
                <TR>
                  <TH>Invoice</TH>
                  <TH>Customer</TH>
                  <TH>Due</TH>
                  <TH className="text-right">Outstanding</TH>
                </TR>
              </THead>
              <TBody>
                {s?.top_overdue.map((i) => (
                  <TR key={i.id}>
                    <TD>
                      <Link
                        className="font-mono text-xs text-sage-deep hover:underline"
                        to={`/invoices/${i.id}`}
                      >
                        {i.invoice_number}
                      </Link>
                    </TD>
                    <TD>{i.customer_name ?? "—"}</TD>
                    <TD>
                      {formatDate(i.due_date)}
                      <span className="ml-1 text-xs text-danger">
                        (+{i.days_overdue}d)
                      </span>
                    </TD>
                    <TD className="text-right">{formatMoney(i.outstanding)}</TD>
                  </TR>
                ))}
                {s && s.top_overdue.length === 0 && (
                  <TR>
                    <TD colSpan={4} className="text-center text-cream0">
                      Nothing overdue. <StatusBadge status="success" />
                    </TD>
                  </TR>
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
