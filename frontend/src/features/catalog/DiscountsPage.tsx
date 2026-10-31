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
import { formatDate, formatMoney } from "../../lib/utils";

interface Discount {
  id: string;
  name: string;
  code: string;
  discount_type: string;
  discount_value: string;
  start_date: string;
  expiry_date: string | null;
  minimum_purchase_amount: string;
  min_quantity: string;
  usage_limit: number | null;
  usage_count: number;
  is_active: boolean;
}
interface ListResp { items: Discount[]; total: number; pages: number }

const EMPTY = {
  name: "", code: "", discount_type: "percentage", discount_value: "",
  start_date: "", expiry_date: "", minimum_purchase_amount: "0",
  min_quantity: "0", usage_limit: "",
};

export default function DiscountsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const discounts = useQuery({
    queryKey: ["discounts", page],
    queryFn: () => api<ListResp>(`/discounts${qs({ page, page_size: 15 })}`),
  });

  const create = useMutation({
    mutationFn: () =>
      api<Discount>("/discounts", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          expiry_date: form.expiry_date || null,
          usage_limit: form.usage_limit ? Number(form.usage_limit) : null,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discounts"] });
      setOpen(false); setForm(EMPTY); setError(null);
      toast("success", "Discount created");
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  const toggle = useMutation({
    mutationFn: (d: Discount) =>
      api(`/discounts/${d.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !d.is_active }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discounts"] });
      toast("success", "Discount updated");
    },
  });

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <div>
      <PageHeader
        title="Discounts"
        description="Fixed and percentage discounts with purchase, quantity and usage rules."
        actions={<Button onClick={() => setOpen(true)}>New discount</Button>}
      />
      <Card>
        <CardContent className="pt-5">
          {discounts.isLoading && <TableSkeleton />}
          {discounts.data && discounts.data.items.length === 0 && <Empty text="No discounts yet." />}
          {discounts.data && discounts.data.items.length > 0 && (
            <>
              <Table>
                <THead>
                  <TR><TH>Code</TH><TH>Name</TH><TH>Type</TH><TH className="text-right">Value</TH><TH>Valid</TH><TH className="text-right">Used</TH><TH>Status</TH><TH /></TR>
                </THead>
                <TBody>
                  {discounts.data.items.map((d) => (
                    <TR key={d.id}>
                      <TD className="font-medium text-ink">{d.code}</TD>
                      <TD>{d.name}</TD>
                      <TD className="capitalize">{d.discount_type.replace("_", " ")}</TD>
                      <TD className="text-right">
                        {d.discount_type === "percentage" ? `${d.discount_value}%` : formatMoney(Number(d.discount_value))}
                      </TD>
                      <TD className="text-ink-muted">
                        {formatDate(d.start_date)}{d.expiry_date ? ` → ${formatDate(d.expiry_date)}` : " →"}
                      </TD>
                      <TD className="text-right">{d.usage_count}{d.usage_limit ? `/${d.usage_limit}` : ""}</TD>
                      <TD><StatusBadge status={d.is_active ? "active" : "closed"} /></TD>
                      <TD className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => toggle.mutate(d)}>
                          {d.is_active ? "Deactivate" : "Activate"}
                        </Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              {discounts.data.pages > 1 && (
                <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
                  <span>{discounts.data.total} discounts</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                    <Button size="sm" variant="outline" disabled={page >= discounts.data.pages} onClick={() => setPage(page + 1)}>Next</Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New discount" wide>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label>Name</Label><Input required value={form.name} onChange={set("name")} /></div>
            <div className="space-y-1"><Label>Code</Label><Input required value={form.code} onChange={set("code")} /></div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Select value={form.discount_type} onChange={set("discount_type")}>
                <option value="percentage">Percentage</option>
                <option value="fixed_amount">Fixed amount</option>
              </Select>
            </div>
            <div className="space-y-1"><Label>Value</Label><Input required type="number" step="0.01" min="0" value={form.discount_value} onChange={set("discount_value")} /></div>
            <div className="space-y-1"><Label>Start date</Label><Input required type="date" value={form.start_date} onChange={set("start_date")} /></div>
            <div className="space-y-1"><Label>Expiry date</Label><Input type="date" value={form.expiry_date} onChange={set("expiry_date")} /></div>
            <div className="space-y-1"><Label>Min purchase amount</Label><Input type="number" step="0.01" min="0" value={form.minimum_purchase_amount} onChange={set("minimum_purchase_amount")} /></div>
            <div className="space-y-1"><Label>Min quantity</Label><Input type="number" step="0.01" min="0" value={form.min_quantity} onChange={set("min_quantity")} /></div>
            <div className="space-y-1"><Label>Usage limit</Label><Input type="number" min="1" placeholder="Unlimited" value={form.usage_limit} onChange={set("usage_limit")} /></div>
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
