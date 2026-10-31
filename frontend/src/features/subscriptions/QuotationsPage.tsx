import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, qs } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Select } from "../../components/ui/select";
import { StatusBadge } from "../../components/ui/badge";
import { Modal, PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { useToast } from "../../components/ui/toast";
import { formatDate, formatMoney } from "../../lib/utils";

interface Quotation {
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
}
interface Page<T> { items: T[]; total: number; page: number; page_size: number }
interface Customer { id: string; name: string; email: string }
interface CustPage { items: Customer[] }
interface Template { id: string; name: string }
interface TplPage { items: Template[] }

export default function QuotationsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ customer_id: "", template_id: "", notes: "" });
  const [error, setError] = useState<string | null>(null);

  const quotes = useQuery({
    queryKey: ["quotations", page, status],
    queryFn: () => api<Page<Quotation>>(`/quotations${qs({ page, page_size: 15, status })}`),
  });
  const customers = useQuery({
    queryKey: ["customers-all"],
    queryFn: () => api<CustPage>("/customers?page_size=100"),
  });
  const templates = useQuery({
    queryKey: ["quote-templates"],
    queryFn: () => api<TplPage>("/quotation-templates?page_size=100"),
  });

  const create = useMutation({
    mutationFn: () =>
      api<Quotation>("/quotations", {
        method: "POST",
        body: JSON.stringify({
          customer_id: form.customer_id,
          template_id: form.template_id || null,
          notes: form.notes || null,
        }),
      }),
    onSuccess: (q) => {
      qc.invalidateQueries({ queryKey: ["quotations"] });
      setOpen(false); setForm({ customer_id: "", template_id: "", notes: "" });
      setError(null);
      toast("success", `Quotation ${q.quotation_number} created`);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  return (
    <div>
      <PageHeader
        title="Quotations"
        description="Quotes sent to customers; confirm to convert into a subscription."
        actions={<Button onClick={() => setOpen(true)}>New quotation</Button>}
      />
      <Card>
        <CardContent className="pt-5">
          <div className="mb-4">
            <Select
              className="max-w-xs"
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            >
              <option value="">All statuses</option>
              {["draft", "sent", "confirmed", "converted", "expired", "cancelled"].map((s) => (
                <option key={s} value={s} className="capitalize">{s}</option>
              ))}
            </Select>
          </div>
          {quotes.isLoading && <TableSkeleton />}
          {quotes.data && quotes.data.items.length === 0 && (
            <Empty text="No quotations." hint="Create a quotation to start a new subscription." />
          )}
          {quotes.data && quotes.data.items.length > 0 && (
            <>
              <Table>
                <THead>
                  <TR><TH>Number</TH><TH>Status</TH><TH>Issued</TH><TH>Valid until</TH><TH className="text-right">Subtotal</TH><TH className="text-right">Total</TH><TH /></TR>
                </THead>
                <TBody>
                  {quotes.data.items.map((q) => (
                    <TR key={q.id}>
                      <TD><Link className="font-medium text-ink underline-offset-2 hover:underline" to={`/quotations/${q.id}`}>{q.quotation_number}</Link></TD>
                      <TD><StatusBadge status={q.status} /></TD>
                      <TD>{formatDate(q.issue_date)}</TD>
                      <TD>{formatDate(q.valid_until)}</TD>
                      <TD className="text-right">{formatMoney(Number(q.subtotal))}</TD>
                      <TD className="text-right font-medium text-ink">{formatMoney(Number(q.total_amount))}</TD>
                      <TD className="text-right">
                        <Link to={`/quotations/${q.id}`}><Button size="sm" variant="ghost">Open</Button></Link>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
                <span>{quotes.data.total} quotations</span>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                  <Button size="sm" variant="outline" disabled={quotes.data.items.length < 15} onClick={() => setPage(page + 1)}>Next</Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New quotation">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="space-y-1">
            <Label>Customer</Label>
            <Select required value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
              <option value="">Select…</option>
              {customers.data?.items.map((c) => (
                <option key={c.id} value={c.id}>{c.name} — {c.email}</option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Template (optional)</Label>
            <Select value={form.template_id} onChange={(e) => setForm({ ...form, template_id: e.target.value })}>
              <option value="">None</option>
              {templates.data?.items.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
            <p className="text-xs text-ink-muted">Template lines are copied onto the quotation.</p>
          </div>
          <div className="space-y-1"><Label>Notes</Label><Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create"}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
