import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import type {
  BillingRun,
  BillingRunResult,
  DueSubscription,
  Page,
} from "../../api/types";
import { StatusBadge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { formatDate } from "../../lib/utils";

export default function BillingPage() {
  const qc = useQueryClient();
  const [runDate, setRunDate] = useState("");

  const due = useQuery({
    queryKey: ["due-subscriptions"],
    queryFn: () => api<DueSubscription[]>("/billing/due"),
  });

  const runs = useQuery({
    queryKey: ["billing-runs"],
    queryFn: () => api<Page<BillingRun>>("/billing/runs?page_size=20"),
  });

  const run = useMutation({
    mutationFn: () =>
      api<BillingRunResult>("/billing/runs", {
        method: "POST",
        body: JSON.stringify({ run_for_date: runDate || undefined }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["billing-runs"] });
      qc.invalidateQueries({ queryKey: ["due-subscriptions"] });
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Recurring billing</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="run-date">Run for date (empty = today)</Label>
              <Input
                id="run-date"
                type="date"
                value={runDate}
                onChange={(e) => setRunDate(e.target.value)}
              />
            </div>
            <Button onClick={() => run.mutate()} disabled={run.isPending}>
              {run.isPending ? "Running…" : "Run billing now"}
            </Button>
            {run.data && (
              <span className="text-sm text-ink-muted">
                Generated {run.data.generated}, skipped {run.data.skipped},
                failed {run.data.failed}, remaining {run.data.remaining}.
              </span>
            )}
            {run.isError && (
              <span className="text-sm text-danger">Run failed.</span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Due subscriptions ({due.data?.length ?? 0})</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Subscription</TH>
                <TH>Customer</TH>
                <TH>Frequency</TH>
                <TH>Next billing date</TH>
                <TH>Expiry</TH>
                <TH className="text-right">Lines</TH>
              </TR>
            </THead>
            <TBody>
              {due.data?.map((s) => (
                <TR key={s.subscription_id}>
                  <TD className="font-mono text-xs">{s.subscription_id}</TD>
                  <TD>{s.customer_name ?? s.customer_id.slice(0, 8)}</TD>
                  <TD className="capitalize">{s.billing_frequency}</TD>
                  <TD>{formatDate(s.next_billing_date)}</TD>
                  <TD>{s.expiry_date ? formatDate(s.expiry_date) : "—"}</TD>
                  <TD className="text-right">{s.line_count}</TD>
                </TR>
              ))}
              {due.data?.length === 0 && (
                <TR>
                  <TD colSpan={6} className="py-8 text-center text-cream0">
                    Nothing due — all caught up.
                  </TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Run history</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Started</TH>
                <TH>For date</TH>
                <TH>Trigger</TH>
                <TH>Status</TH>
                <TH className="text-right">Scanned</TH>
                <TH className="text-right">Generated</TH>
                <TH className="text-right">Skipped</TH>
                <TH className="text-right">Failed</TH>
              </TR>
            </THead>
            <TBody>
              {runs.data?.items.map((r) => (
                <TR key={r.id}>
                  <TD>{formatDate(r.started_at)}</TD>
                  <TD>{formatDate(r.run_for_date)}</TD>
                  <TD className="capitalize">{r.trigger_source}</TD>
                  <TD>
                    <StatusBadge status={r.status} />
                  </TD>
                  <TD className="text-right">{r.scanned}</TD>
                  <TD className="text-right">{r.generated}</TD>
                  <TD className="text-right">{r.skipped}</TD>
                  <TD className="text-right">{r.failed}</TD>
                </TR>
              ))}
              {runs.data?.items.length === 0 && (
                <TR>
                  <TD colSpan={8} className="py-8 text-center text-cream0">
                    No runs yet.
                  </TD>
                </TR>
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
