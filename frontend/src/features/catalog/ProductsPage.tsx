import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, qs } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { StatusBadge } from "../../components/ui/badge";
import { Modal, PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { useToast } from "../../components/ui/toast";
import { formatMoney } from "../../lib/utils";

interface Product {
  id: number;
  name: string;
  product_type: string;
  sales_price: string;
  cost_price: string;
  notes: string | null;
  tax_id: string | null;
  is_active: boolean;
  variants: { id: number; name: string }[];
}
interface ListResp { items: Product[]; total: number; pages: number }

const EMPTY = { name: "", product_type: "service", sales_price: "", cost_price: "", notes: "" };

export default function ProductsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const products = useQuery({
    queryKey: ["products", search, page],
    queryFn: () =>
      api<ListResp>(`/products${qs({ search, page, page_size: 15 })}`),
  });

  const create = useMutation({
    mutationFn: () =>
      api<Product>("/products", { method: "POST", body: JSON.stringify(form) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      setOpen(false); setForm(EMPTY); setError(null);
      toast("success", "Product created");
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  const toggle = useMutation({
    mutationFn: (p: Product) =>
      api(`/products/${p.id}`, { method: "PUT", body: JSON.stringify({ is_active: !p.is_active }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      toast("success", "Product updated");
    },
  });

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <div>
      <PageHeader
        title="Products"
        description="Manage the product catalog used by plans, quotations and invoices."
        actions={<Button onClick={() => setOpen(true)}>New product</Button>}
      />
      <Card>
        <CardContent className="pt-5">
          <div className="mb-4 flex gap-2">
            <Input
              placeholder="Search products…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="max-w-xs"
            />
          </div>
          {products.isLoading && <TableSkeleton />}
          {products.data && products.data.items.length === 0 && (
            <Empty text="No products yet." hint="Create the first product to start building plans." />
          )}
          {products.data && products.data.items.length > 0 && (
            <>
              <Table>
                <THead>
                  <TR><TH>Name</TH><TH>Type</TH><TH>Variants</TH><TH className="text-right">Sale price</TH><TH className="text-right">Cost</TH><TH>Status</TH><TH /></TR>
                </THead>
                <TBody>
                  {products.data.items.map((p) => (
                    <TR key={p.id}>
                      <TD className="font-medium text-ink">{p.name}</TD>
                      <TD>{p.product_type}</TD>
                      <TD>{p.variants.length}</TD>
                      <TD className="text-right">{formatMoney(Number(p.sales_price))}</TD>
                      <TD className="text-right">{formatMoney(Number(p.cost_price))}</TD>
                      <TD><StatusBadge status={p.is_active ? "active" : "closed"} /></TD>
                      <TD className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => toggle.mutate(p)}>
                          {p.is_active ? "Deactivate" : "Activate"}
                        </Button>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              {products.data.pages > 1 && (
                <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
                  <span>{products.data.total} products</span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                    <Button size="sm" variant="outline" disabled={page >= products.data.pages} onClick={() => setPage(page + 1)}>Next</Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New product">
        <form
          className="space-y-4"
          onSubmit={(e) => { e.preventDefault(); create.mutate(); }}
        >
          <div className="space-y-1"><Label>Name</Label><Input required value={form.name} onChange={set("name")} /></div>
          <div className="space-y-1"><Label>Type</Label><Input required placeholder="service / good" value={form.product_type} onChange={set("product_type")} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label>Sales price</Label><Input required type="number" step="0.01" min="0" value={form.sales_price} onChange={set("sales_price")} /></div>
            <div className="space-y-1"><Label>Cost price</Label><Input required type="number" step="0.01" min="0" value={form.cost_price} onChange={set("cost_price")} /></div>
          </div>
          <div className="space-y-1"><Label>Notes</Label><Input value={form.notes} onChange={set("notes")} /></div>
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
