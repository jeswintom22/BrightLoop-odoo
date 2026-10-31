import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { InvoiceSummary, Page, Payment } from "../../api/types";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { StatusBadge } from "../../components/ui/badge";
import { PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import {
  Table, TBody, TD, TH, THead, TR,
} from "../../components/ui/table";
import { formatDate, formatMoney } from "../../lib/utils";

interface PortalSub {
  id: string;
  subscription_number: string;
  status: string;
  billing_frequency: string;
  start_date: string | null;
  expiry_date: string | null;
  next_billing_date: string | null;
}

export default function PortalPage({ section }: { section?: "subscriptions" | "invoices" | "payments" }) {
  const show = (s: string) => !section || section === s;

  const subs = useQuery({
    queryKey: ["portal-subs"],
    queryFn: () => api<PortalSub[]>("/portal/subscriptions"),
    enabled: show("subscriptions"),
  });
  const invoices = useQuery({
    queryKey: ["portal-invoices"],
    queryFn: () => api<Page<InvoiceSummary>>("/portal/invoices?page_size=20"),
    enabled: show("invoices"),
  });
  const payments = useQuery({
    queryKey: ["portal-payments"],
    queryFn: () => api<Page<Payment>>("/portal/payments?page_size=20"),
    enabled: show("payments"),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={section === "invoices" ? "My invoices" : section === "payments" ? "My payments" : "My account"}
        description={!section ? "Subscriptions, invoices and payments for your account." : undefined}
      />

      {show("subscriptions") && (
      <Card>
        <CardHeader><CardTitle>My subscriptions</CardTitle></CardHeader>
        <CardContent>
          {subs.isLoading && <TableSkeleton />}
          {subs.data?.length === 0 && <Empty text="No subscriptions yet." />}
          {subs.data && subs.data.length > 0 && (
            <Table>
              <THead>
                <TR><TH>Number</TH><TH>Status</TH><TH>Frequency</TH><TH>Started</TH><TH>Next billing</TH><TH>Expires</TH></TR>
              </THead>
              <TBody>
                {subs.data.map((s) => (
                  <TR key={s.id}>
                    <TD className="font-medium text-ink">{s.subscription_number}</TD>
                    <TD><StatusBadge status={s.status} /></TD>
                    <TD className="capitalize">{s.billing_frequency}</TD>
                    <TD>{formatDate(s.start_date)}</TD>
                    <TD>{formatDate(s.next_billing_date)}</TD>
                    <TD>{formatDate(s.expiry_date)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
      )}

      {show("invoices") && (
      <Card>
        <CardHeader><CardTitle>My invoices</CardTitle></CardHeader>
        <CardContent>
          {invoices.isLoading && <TableSkeleton />}
          {invoices.data?.items.length === 0 && <Empty text="No invoices yet." />}
          {invoices.data && invoices.data.items.length > 0 && (
            <Table>
              <THead>
                <TR><TH>Invoice</TH><TH>Status</TH><TH>Issued</TH><TH>Due</TH><TH className="text-right">Total</TH><TH className="text-right">Balance</TH></TR>
              </THead>
              <TBody>
                {invoices.data.items.map((i) => (
                  <TR key={i.id}>
                    <TD>
                      <Link to={`/portal/invoices/${i.id}`} className="font-medium text-sage-deep hover:underline">
                        {i.invoice_number}
                      </Link>
                    </TD>
                    <TD><StatusBadge status={i.status} /></TD>
                    <TD>{formatDate(i.issue_date)}</TD>
                    <TD>{formatDate(i.due_date)}</TD>
                    <TD className="text-right">{formatMoney(i.total_amount, i.currency)}</TD>
                    <TD className="text-right">{formatMoney(i.outstanding, i.currency)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
      )}

      {show("payments") && (
      <Card>
        <CardHeader><CardTitle>Payment history</CardTitle></CardHeader>
        <CardContent>
          {payments.isLoading && <TableSkeleton />}
          {payments.data?.items.length === 0 && <Empty text="No payments yet." />}
          {payments.data && payments.data.items.length > 0 && (
            <Table>
              <THead>
                <TR><TH>Reference</TH><TH>Date</TH><TH>Method</TH><TH className="text-right">Amount</TH></TR>
              </THead>
              <TBody>
                {payments.data.items.map((p) => (
                  <TR key={p.id}>
                    <TD className="font-medium text-ink">{p.payment_reference}</TD>
                    <TD>{formatDate(p.paid_at)}</TD>
                    <TD className="capitalize">{p.method}</TD>
                    <TD className="text-right">{formatMoney(p.amount)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
      )}
    </div>
  );
}
