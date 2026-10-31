import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, qs, ApiError } from "../../api/client";
import type { InvoiceDetail, InvoiceSummary, Page } from "../../api/types";
import { StatusBadge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Select } from "../../components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { formatDate, formatMoney } from "../../lib/utils";

export default function InvoicesPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [page, setPage] = useState(1);
  const [subId, setSubId] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["invoices", q, status, overdue, page],
    queryFn: () =>
      api<Page<InvoiceSummary>>(
        `/invoices${qs({ q, status, overdue: overdue || undefined, page, page_size: 20 })}`,
      ),
  });

  const create = useMutation({
    mutationFn: (subscription_id: string) =>
      api<InvoiceDetail>("/invoices", {
        method: "POST",
        body: JSON.stringify({ subscription_id }),
      }),
    onSuccess: () => {
      setSubId("");
      setCreateError(null);
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["due-subscriptions"] });
    },
    onError: (e) =>
      setCreateError(e instanceof ApiError ? `${e.code}: ${e.message}` : "Failed"),
  });

  const totalPages = list.data ? Math.ceil(list.data.total / 20) : 1;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Generate invoice</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (subId.trim()) create.mutate(subId.trim());
            }}
          >
            <div className="w-96">
              <Label htmlFor="sub-id">Subscription ID</Label>
              <Input
                id="sub-id"
                placeholder="uuid — see Billing runs → Due subscriptions"
                value={subId}
                onChange={(e) => setSubId(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={create.isPending || !subId.trim()}>
              {create.isPending ? "Generating…" : "Generate"}
            </Button>
            {create.isSuccess && (
              <span className="text-sm text-success">
                Invoice created as draft.
              </span>
            )}
            {createError && (
              <span className="text-sm text-danger">{createError}</span>
            )}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-64">
              <Label htmlFor="q">Search</Label>
              <Input
                id="q"
                placeholder="Invoice number…"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
              />
            </div>
            <div className="w-44">
              <Label htmlFor="status">Status</Label>
              <Select
                id="status"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All</option>
                <option value="draft">Draft</option>
                <option value="confirmed">Confirmed</option>
                <option value="paid">Paid</option>
                <option value="cancelled">Cancelled</option>
              </Select>
            </div>
            <label className="flex items-center gap-2 pb-2 text-sm">
              <input
                type="checkbox"
                checked={overdue}
                onChange={(e) => {
                  setOverdue(e.target.checked);
                  setPage(1);
                }}
              />
              Overdue only
            </label>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Number</TH>
                <TH>Customer</TH>
                <TH>Status</TH>
                <TH>Issued</TH>
                <TH>Due</TH>
                <TH className="text-right">Total</TH>
                <TH className="text-right">Outstanding</TH>
              </TR>
            </THead>
            <TBody>
              {list.data?.items.map((inv) => (
                <TR key={inv.id}>
                  <TD>
                    <Link
                      className="font-mono text-xs text-sage-deep hover:underline"
                      to={`/invoices/${inv.id}`}
                    >
                      {inv.invoice_number}
                    </Link>
                  </TD>
                  <TD>{inv.customer_name ?? inv.customer_id.slice(0, 8)}</TD>
                  <TD>
                    <StatusBadge status={inv.status} />
                  </TD>
                  <TD>{formatDate(inv.issue_date)}</TD>
                  <TD>{formatDate(inv.due_date)}</TD>
                  <TD className="text-right">
                    {formatMoney(inv.total_amount, inv.currency)}
                  </TD>
                  <TD className="text-right">
                    {formatMoney(inv.outstanding, inv.currency)}
                  </TD>
                </TR>
              ))}
              {list.data?.items.length === 0 && (
                <TR>
                  <TD colSpan={7} className="py-8 text-center text-cream0">
                    No invoices match these filters.
                  </TD>
                </TR>
              )}
            </TBody>
          </Table>
          <div className="mt-3 flex items-center justify-between text-sm text-ink-muted">
            <span>
              {list.data?.total ?? 0} invoices · page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
