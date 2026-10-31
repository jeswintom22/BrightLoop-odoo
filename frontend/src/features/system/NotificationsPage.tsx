import { useQuery } from "@tanstack/react-query";
import { api, qs } from "../../api/client";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { StatusBadge } from "../../components/ui/badge";
import { PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { formatDate } from "../../lib/utils";

interface Invoice {
  id: string;
  invoice_number: string;
  customer_name: string | null;
  status: string;
  due_date: string;
}
interface InvPage { items: Invoice[]; total: number }
interface BillingRun {
  id: string;
  run_for_date: string;
  status: string;
  scanned: number;
  generated: number;
  skipped: number;
}
interface RunPage { items: BillingRun[] }

export default function NotificationsPage() {
  const invoices = useQuery({
    queryKey: ["notif-invoices"],
    queryFn: () => api<InvPage>(`/invoices${qs({ page_size: 15 })}`),
  });
  const runs = useQuery({
    queryKey: ["notif-runs"],
    queryFn: () => api<RunPage>("/billing/runs?page_size=10"),
  });

  return (
    <div>
      <PageHeader
        title="Notifications"
        description="Recent invoice and billing activity. A dedicated notification centre and preferences are not yet exposed by the backend."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Recent invoices</CardTitle></CardHeader>
          <CardContent>
            {invoices.isLoading && <TableSkeleton />}
            {invoices.data?.items.length === 0 && <Empty text="No invoices yet." />}
            {invoices.data && invoices.data.items.length > 0 && (
              <Table>
                <THead><TR><TH>Invoice</TH><TH>Customer</TH><TH>Status</TH><TH>Due</TH></TR></THead>
                <TBody>
                  {invoices.data.items.map((i) => (
                    <TR key={i.id}>
                      <TD className="font-medium text-ink">{i.invoice_number}</TD>
                      <TD>{i.customer_name ?? "—"}</TD>
                      <TD><StatusBadge status={i.status} /></TD>
                      <TD>{formatDate(i.due_date)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Billing run activity</CardTitle></CardHeader>
          <CardContent>
            {runs.isLoading && <TableSkeleton />}
            {runs.data?.items.length === 0 && <Empty text="No billing runs yet." />}
            {runs.data && runs.data.items.length > 0 && (
              <Table>
                <THead><TR><TH>Run date</TH><TH>Status</TH><TH className="text-right">Scanned</TH><TH className="text-right">Generated</TH><TH className="text-right">Skipped</TH></TR></THead>
                <TBody>
                  {runs.data.items.map((r) => (
                    <TR key={r.id}>
                      <TD className="font-medium text-ink">{formatDate(r.run_for_date)}</TD>
                      <TD><StatusBadge status={r.status} /></TD>
                      <TD className="text-right">{r.scanned}</TD>
                      <TD className="text-right">{r.generated}</TD>
                      <TD className="text-right">{r.skipped}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
