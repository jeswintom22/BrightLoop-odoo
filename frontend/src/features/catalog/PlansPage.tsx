import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
import { formatMoney } from "../../lib/utils";

interface Plan {
  id: string;
  name: string;
  product_id: number;
  price: string;
  billing_frequency: string;
  minimum_quantity: number;
  available_from: string;
  available_until: string | null;
  status: string;
  allow_pause: boolean;
  allow_renewal: boolean;
  allow_early_closure: boolean;
  automatic_closure: boolean;
}
interface ListResp { items: Plan[]; total: number; pages: number }
interface ProductOpt { id: number; name: string }
interface ProdList { items: ProductOpt[] }

const FREQS = ["daily", "weekly", "monthly", "yearly"];
const EMPTY = {
  name: "", product_id: "", price: "", billing_frequency: "monthly",
  minimum_quantity: "1", available_from: "",
};

export default function PlansPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [flags, setFlags] = useState({ allow_pause: true, allow_renewal: true, allow_early_closure: true, automatic_closure: false });
  const [error, setError] = useState<string | null>(null);

  const plans = useQuery({
    queryKey: ["plans", page],
    queryFn: () => api<ListResp>(`/plans${qs({ page, page_size: 15 })}`),
  });
  const products = useQuery({
    queryKey: ["products-all"],
    queryFn: () => api<ProdList>("/products?page_size=100"),
  });

  const create = useMutation({
    mutationFn: () =>
      api<Plan>("/plans", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          product_id: Number(form.product_id),
          minimum_quantity: Number(form.minimum_quantity),
          ...flags,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      setOpen(false); setForm(EMPTY); setError(null);
      toast("success", "Plan created");
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  const toggleStatus = useMutation({
    mutationFn: (p: Plan) =>
      api(`/plans/${p.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: p.status === "active" ? "archived" : "active" }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      toast("success", "Plan updated");
    },
  });

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <div>
      <PageHeader
        title="Subscription Plans"
        description="Billing frequencies, availability windows and lifecycle permissions."
        actions={<Button onClick={() => setOpen(true)}>New plan</Button>}
      />
      <Card>
        <CardContent className="pt-5">
          {plans.isLoading && <TableSkeleton />}
          {plans.data && plans.data.items.length === 0 && <Empty text="No plans yet." hint="Create a product first, then a plan." />}
          {plans.data && plans.data.items.length > 0 && (
            <>
              <Table>
                <THead>
                  <TR><TH>Name</TH><TH>Frequency</TH><TH className="text-right">Price</TH><TH className="text-right">Min qty</TH><TH>Available</TH><TH>Status</TH><TH /></TR>
                </THead>
                <TBody>
                  {plans.data.items.map((p) => (
                    <TR key={p.id}>
                      <TD className="font-medium text-ink">{p.name}</TD>
                      <TD className="capitalize">{p.billing_frequency}</TD>
                      <TD className="text-right">{formatMoney(Number(p.price))}</TD>
                      <TD className="text-right">{p.minimum_quantity}</TD>
                      <TD className="text-ink-muted">
                        {p.available_from}{p.available_until ? ` → ${p.available_until}` : " →"}
                      </TD>
                      <TD><StatusBadge status={p.status} /></TD>
                      <TD className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => toggleStatus.mutate(p)}>
                          {p.status === "active" ? "Archive" : "Activate"}
                        </Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              {plans.data.pages > 1 && (
                <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
                  <span>{plans.data.total} plans</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                    <Button size="sm" variant="outline" disabled={page >= plans.data.pages} onClick={() => setPage(page + 1)}>Next</Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New subscription plan" wide>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label>Name</Label><Input required value={form.name} onChange={set("name")} /></div>
            <div className="space-y-1">
              <Label>Product</Label>
              <Select required value={form.product_id} onChange={set("product_id")}>
                <option value="">Select…</option>
                {products.data?.items.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-1"><Label>Price</Label><Input required type="number" step="0.01" min="0" value={form.price} onChange={set("price")} /></div>
            <div className="space-y-1">
              <Label>Billing frequency</Label>
              <Select value={form.billing_frequency} onChange={set("billing_frequency")}>
                {FREQS.map((f) => <option key={f} value={f} className="capitalize">{f}</option>)}
              </Select>
            </div>
            <div className="space-y-1"><Label>Minimum quantity</Label><Input required type="number" min="1" value={form.minimum_quantity} onChange={set("minimum_quantity")} /></div>
            <div className="space-y-1"><Label>Available from</Label><Input required type="date" value={form.available_from} onChange={set("available_from")} /></div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {(Object.keys(flags) as (keyof typeof flags)[]).map((k) => (
              <label key={k} className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={flags[k]}
                  onChange={(e) => setFlags({ ...flags, [k]: e.target.checked })}
                  className="h-4 w-4 accent-sage-deep"
                />
                {k.replace(/_/g, " ")}
              </label>
            ))}
          </div>
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
