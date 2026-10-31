import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import type { InvoiceDetail } from "../../api/types";
import { StatusBadge } from "../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { formatDate, formatMoney } from "../../lib/utils";

export default function PortalInvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const invoice = useQuery({
    queryKey: ["portal-invoice", id],
    queryFn: () => api<InvoiceDetail>(`/portal/invoices/${id}`),
  });

  if (invoice.isLoading) return <p className="py-10 text-center text-slate-500">Loading…</p>;
  if (invoice.error || !invoice.data)
    return <p className="py-10 text-center text-red-600">Invoice not found.</p>;
  const inv = invoice.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{inv.invoice_number}</h1>
        <Link to="/portal" className="text-sm text-slate-600 hover:underline">← Back</Link>
      </div>
      <Card>
        <CardContent className="grid grid-cols-2 gap-4 py-4 sm:grid-cols-4">
          <div><p className="text-xs text-slate-500">Status</p><StatusBadge status={inv.status} /></div>
          <div><p className="text-xs text-slate-500">Issued</p><p>{formatDate(inv.issue_date)}</p></div>
          <div><p className="text-xs text-slate-500">Due</p><p>{formatDate(inv.due_date)}</p></div>
          <div>
            <p className="text-xs text-slate-500">Balance</p>
            <p className="font-semibold">{formatMoney(inv.outstanding, inv.currency)}</p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Line items</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <THead><TR><TH>Description</TH><TH className="text-right">Qty</TH><TH className="text-right">Unit</TH><TH className="text-right">Total</TH></TR></THead>
            <TBody>
              {inv.lines.map((l) => (
                <TR key={l.id}>
                  <TD>{l.description}</TD>
                  <TD className="text-right">{l.quantity}</TD>
                  <TD className="text-right">{formatMoney(l.unit_price, inv.currency)}</TD>
                  <TD className="text-right">{formatMoney(l.line_total, inv.currency)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <div className="mt-4 space-y-1 text-right text-sm">
            <p>Subtotal: {formatMoney(inv.subtotal, inv.currency)}</p>
            <p>Tax: {formatMoney(inv.tax_total, inv.currency)}</p>
            <p>Discount: −{formatMoney(inv.discount_total, inv.currency)}</p>
            <p className="text-base font-semibold">Total: {formatMoney(inv.total_amount, inv.currency)}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
