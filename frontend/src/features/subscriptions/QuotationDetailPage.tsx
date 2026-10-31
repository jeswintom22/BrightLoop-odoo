import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { StatusBadge } from "../../components/ui/badge";
import { ConfirmDialog, PageHeader } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { useToast } from "../../components/ui/toast";
import { formatDate, formatMoney } from "../../lib/utils";

interface QuotationDetail {
  id: string;
  quotation_number: string;
  customer_id: string;
  status: string;
  issue_date: string;
  valid_until: string;
  subtotal: string;
  tax_total: string;
  discount_total: string;
  total_amount: string;
  notes: string | null;
  lines: {
    id: string;
    description: string;
    quantity: string;
    unit_price: string;
    tax_rate: string;
    line_total: string;
  }[];
}

type PendingAction = "send" | "confirm" | "convert" | null;

export default function QuotationDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const toast = useToast();
  const [pending, setPending] = useState<PendingAction>(null);
  const [error, setError] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["quotation", id],
    queryFn: () => api<QuotationDetail>(`/quotations/${id}`),
  });

  const act = useMutation({
    mutationFn: (action: PendingAction) =>
      api(`/quotations/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify(action === "convert" ? {} : undefined),
      }),
    onSuccess: (_d, action) => {
      qc.invalidateQueries({ queryKey: ["quotation", id] });
      qc.invalidateQueries({ queryKey: ["quotations"] });
      setPending(null); setError(null);
      toast("success", action === "convert" ? "Subscription created" : `Quotation ${action === "send" ? "sent" : "confirmed"}`);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  const d = q.data;
  if (q.isLoading) return <p className="py-10 text-center text-sm text-ink-muted">Loading…</p>;
  if (!d) return <p className="py-10 text-center text-sm text-ink-muted">Quotation not found.</p>;

  const actions: { key: PendingAction; label: string; when: boolean }[] = [
    { key: "send", label: "Send", when: d.status === "draft" },
    { key: "confirm", label: "Confirm", when: d.status === "draft" || d.status === "sent" },
    { key: "convert", label: "Convert to subscription", when: d.status === "confirmed" },
  ];

  return (
    <div>
      <PageHeader
        title={d.quotation_number}
        description={`Issued ${formatDate(d.issue_date)} · valid until ${formatDate(d.valid_until)}`}
        actions={
          <div className="flex gap-2">
            {actions.filter((a) => a.when).map((a) => (
              <Button key={a.key} onClick={() => setPending(a.key)}>{a.label}</Button>
            ))}
          </div>
        }
      />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Line items</CardTitle>
          <StatusBadge status={d.status} />
        </CardHeader>
        <CardContent>
          {d.lines.length === 0 && (
            <p className="text-sm text-ink-muted">No line items yet. Lines are added via the API when plans are selected.</p>
          )}
          {d.lines.length > 0 && (
            <Table>
              <THead>
                <TR><TH>Description</TH><TH className="text-right">Qty</TH><TH className="text-right">Unit price</TH><TH className="text-right">Tax rate</TH><TH className="text-right">Total</TH></TR>
              </THead>
              <TBody>
                {d.lines.map((l) => (
                  <TR key={l.id}>
                    <TD className="font-medium text-ink">{l.description || "—"}</TD>
                    <TD className="text-right">{l.quantity}</TD>
                    <TD className="text-right">{formatMoney(Number(l.unit_price))}</TD>
                    <TD className="text-right">{l.tax_rate}%</TD>
                    <TD className="text-right font-medium text-ink">{formatMoney(Number(l.line_total))}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
          <div className="mt-4 flex justify-end">
            <div className="w-64 space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-ink-muted">Subtotal</span><span>{formatMoney(Number(d.subtotal))}</span></div>
              <div className="flex justify-between"><span className="text-ink-muted">Discount</span><span>{formatMoney(Number(d.discount_total))}</span></div>
              <div className="flex justify-between"><span className="text-ink-muted">Tax</span><span>{formatMoney(Number(d.tax_total))}</span></div>
              <div className="flex justify-between border-t border-line pt-1 font-medium text-ink"><span>Total</span><span>{formatMoney(Number(d.total_amount))}</span></div>
            </div>
          </div>
          {d.notes && <p className="mt-4 text-sm text-ink-muted">Notes: {d.notes}</p>}
          {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        </CardContent>
      </Card>
      <p className="mt-4 text-sm"><Link className="text-sage-deep hover:underline" to="/quotations">← Back to quotations</Link></p>

      <ConfirmDialog
        open={pending !== null}
        title={pending === "convert" ? "Convert quotation" : `${pending === "send" ? "Send" : "Confirm"} quotation`}
        message={
          pending === "convert"
            ? `Create an active subscription from ${d.quotation_number}?`
            : `Proceed with "${pending}" on ${d.quotation_number}?`
        }
        onClose={() => setPending(null)}
        onConfirm={() => pending && act.mutate(pending)}
        busy={act.isPending}
      />
    </div>
  );
}
