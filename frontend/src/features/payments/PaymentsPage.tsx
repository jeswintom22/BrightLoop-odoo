import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, qs } from "../../api/client";
import type { Page, Payment } from "../../api/types";
import { StatusBadge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Select } from "../../components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { formatDate, formatMoney } from "../../lib/utils";

export default function PaymentsPage() {
  const qc = useQueryClient();
  const [method, setMethod] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);

  const list = useQuery({
    queryKey: ["payments", method, from, to, page],
    queryFn: () =>
      api<Page<Payment>>(
        `/payments${qs({ method, from, to, page, page_size: 20 })}`,
      ),
  });

  const voidPayment = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api<Payment>(`/payments/${id}/void`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const totalPages = list.data ? Math.ceil(list.data.total / 20) : 1;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-end gap-3">
          <CardTitle className="mr-auto">Payments</CardTitle>
          <div className="w-44">
            <Label htmlFor="method">Method</Label>
            <Select
              id="method"
              value={method}
              onChange={(e) => {
                setMethod(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All</option>
              <option value="upi">UPI</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="from">From</Label>
            <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="to">To</Label>
            <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <THead>
            <TR>
              <TH>Reference</TH>
              <TH>Invoice</TH>
              <TH>Method</TH>
              <TH>Date</TH>
              <TH>Status</TH>
              <TH className="text-right">Amount</TH>
              <TH />
            </TR>
          </THead>
          <TBody>
            {list.data?.items.map((p) => (
              <TR key={p.id}>
                <TD className="font-mono text-xs">{p.payment_reference}</TD>
                <TD>
                  <Link
                    className="text-blue-600 hover:underline"
                    to={`/invoices/${p.invoice_id}`}
                  >
                    {p.invoice_id.slice(0, 8)}…
                  </Link>
                </TD>
                <TD className="capitalize">{p.method.replace("_", " ")}</TD>
                <TD>{formatDate(p.paid_at)}</TD>
                <TD>
                  <StatusBadge status={p.status} />
                </TD>
                <TD className="text-right">{formatMoney(p.amount)}</TD>
                <TD className="text-right">
                  {p.status === "posted" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={voidPayment.isPending}
                      onClick={() => {
                        const reason = window.prompt(
                          "Reason for voiding this payment:",
                        );
                        if (reason) voidPayment.mutate({ id: p.id, reason });
                      }}
                    >
                      Void
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
            {list.data?.items.length === 0 && (
              <TR>
                <TD colSpan={7} className="py-8 text-center text-slate-500">
                  No payments match these filters.
                </TD>
              </TR>
            )}
          </TBody>
        </Table>
        <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
          <span>
            {list.data?.total ?? 0} payments · page {page} of {totalPages}
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
  );
}
