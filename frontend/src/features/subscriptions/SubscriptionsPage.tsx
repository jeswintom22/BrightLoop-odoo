import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, qs } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Select } from "../../components/ui/select";
import { StatusBadge } from "../../components/ui/badge";
import { ConfirmDialog, Modal, PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { useToast } from "../../components/ui/toast";
import { formatDate } from "../../lib/utils";

interface Subscription {
  id: string;
  subscription_number: string;
  customer_id: string;
  plan_id: string | null;
  status: string;
  billing_frequency: string;
  start_date: string | null;
  expiry_date: string | null;
  next_billing_date: string | null;
  payment_terms: string | null;
}
interface Page<T> { items: T[]; total: number; page: number }
interface Customer { id: string; name: string }
interface CustPage { items: Customer[] }

type Action = "pause" | "resume" | "renew" | "close";

const VERB: Record<Action, string> = { pause: "paused", resume: "resumed", renew: "renewed", close: "closed" };

export default function SubscriptionsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [sel, setSel] = useState<Subscription | null>(null);
  const [confirm, setConfirm] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);

  const subs = useQuery({
    queryKey: ["subscriptions", page, status],
    queryFn: () => api<Page<Subscription>>(`/subscriptions${qs({ page, page_size: 15, status })}`),
  });
  const customers = useQuery({
    queryKey: ["customers-all"],
    queryFn: () => api<CustPage>("/customers?page_size=100"),
  });
  const custName = (id: string) => customers.data?.items.find((c) => c.id === id)?.name ?? "—";

  const act = useMutation({
    mutationFn: (action: Action) =>
      api(`/subscriptions/${sel?.id}/${action}`, { method: "POST" }),
    onSuccess: (_d, action) => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      setConfirm(null); setSel(null); setError(null);
      toast("success", `Subscription ${VERB[action]}`);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  const lifecycle: { a: Action; label: string; when: (s: string) => boolean }[] = [
    { a: "pause", label: "Pause", when: (s) => s === "active" },
    { a: "resume", label: "Resume", when: (s) => s === "paused" },
    { a: "renew", label: "Renew", when: (s) => s === "active" || s === "paused" || s === "expired" },
    { a: "close", label: "Close", when: (s) => s !== "closed" },
  ];

  return (
    <div>
      <PageHeader title="Subscriptions" description="Customer subscriptions and lifecycle management." />
      <Card>
        <CardContent className="pt-5">
          <div className="mb-4">
            <Select className="max-w-xs" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">All statuses</option>
              {["active", "paused", "expired", "closed"].map((s) => (
                <option key={s} value={s} className="capitalize">{s}</option>
              ))}
            </Select>
          </div>
          {subs.isLoading && <TableSkeleton />}
          {subs.data && subs.data.items.length === 0 && (
            <Empty text="No subscriptions." hint="Confirm and convert a quotation to create one." />
          )}
          {subs.data && subs.data.items.length > 0 && (
            <>
              <Table>
                <THead>
                  <TR><TH>Number</TH><TH>Customer</TH><TH>Frequency</TH><TH>Status</TH><TH>Started</TH><TH>Next billing</TH><TH /></TR>
                </THead>
                <TBody>
                  {subs.data.items.map((s) => (
                    <TR key={s.id}>
                      <TD className="font-medium text-ink">{s.subscription_number}</TD>
                      <TD>{custName(s.customer_id)}</TD>
                      <TD className="capitalize">{s.billing_frequency}</TD>
                      <TD><StatusBadge status={s.status} /></TD>
                      <TD>{s.start_date ? formatDate(s.start_date) : "—"}</TD>
                      <TD>{s.next_billing_date ? formatDate(s.next_billing_date) : "—"}</TD>
                      <TD className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => { setSel(s); setError(null); }}>Manage</Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
                <span>{subs.data.total} subscriptions</span>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                  <Button size="sm" variant="outline" disabled={subs.data.items.length < 15} onClick={() => setPage(page + 1)}>Next</Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Modal open={sel !== null && confirm === null} onClose={() => { setSel(null); setError(null); }} title={sel?.subscription_number ?? ""}>
        {sel && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><p className="text-ink-muted">Customer</p><p className="font-medium">{custName(sel.customer_id)}</p></div>
              <div><p className="text-ink-muted">Status</p><StatusBadge status={sel.status} /></div>
              <div><p className="text-ink-muted">Started</p><p>{sel.start_date ? formatDate(sel.start_date) : "—"}</p></div>
              <div><p className="text-ink-muted">Expires</p><p>{sel.expiry_date ? formatDate(sel.expiry_date) : "—"}</p></div>
              <div><p className="text-ink-muted">Next billing</p><p>{sel.next_billing_date ? formatDate(sel.next_billing_date) : "—"}</p></div>
              <div><p className="text-ink-muted">Payment terms</p><p>{sel.payment_terms ?? "—"}</p></div>
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-4">
              {lifecycle.filter((l) => l.when(sel.status)).map((l) => (
                <Button key={l.a} variant={l.a === "close" ? "destructive" : "default"} onClick={() => setConfirm(l.a)}>
                  {l.label}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={confirm !== null}
        title={`${confirm === "close" ? "Close" : confirm === "pause" ? "Pause" : confirm === "resume" ? "Resume" : "Renew"} subscription`}
        message={
          confirm === "close"
            ? `Close ${sel?.subscription_number}? This ends billing and cannot be undone.`
            : confirm
              ? `${confirm[0].toUpperCase()}${confirm.slice(1)} ${sel?.subscription_number}?`
              : ""
        }
        confirmLabel={confirm === "close" ? "Close subscription" : "Confirm"}
        destructive={confirm === "close"}
        onClose={() => setConfirm(null)}
        onConfirm={() => confirm && act.mutate(confirm)}
        busy={act.isPending}
      />
    </div>
  );
}
