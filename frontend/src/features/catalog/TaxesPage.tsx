import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { StatusBadge } from "../../components/ui/badge";
import { Modal, PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { useToast } from "../../components/ui/toast";

interface Tax {
  id: string;
  name: string;
  tax_percentage: string;
  description: string | null;
  is_active: boolean;
}
interface ListResp { items: Tax[]; total: number }

export default function TaxesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", tax_percentage: "", description: "" });
  const [error, setError] = useState<string | null>(null);

  const taxes = useQuery({
    queryKey: ["taxes"],
    queryFn: () => api<ListResp>("/taxes"),
  });

  const create = useMutation({
    mutationFn: () =>
      api<Tax>("/taxes", {
        method: "POST",
        body: JSON.stringify({ ...form, description: form.description || null }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["taxes"] });
      setOpen(false); setError(null);
      toast("success", "Tax rule created");
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  const toggle = useMutation({
    mutationFn: (t: Tax) =>
      api(`/taxes/${t.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !t.is_active }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["taxes"] });
      toast("success", "Tax rule updated");
    },
  });

  return (
    <div>
      <PageHeader
        title="Taxes"
        description="Admin-configurable tax rules applied to products and plans."
        actions={<Button onClick={() => setOpen(true)}>New tax rule</Button>}
      />
      <Card>
        <CardContent className="pt-5">
          {taxes.isLoading && <TableSkeleton />}
          {taxes.data && taxes.data.items.length === 0 && <Empty text="No tax rules yet." />}
          {taxes.data && taxes.data.items.length > 0 && (
            <Table>
              <THead><TR><TH>Name</TH><TH className="text-right">Rate</TH><TH>Description</TH><TH>Status</TH><TH /></TR></THead>
              <TBody>
                {taxes.data.items.map((t) => (
                  <TR key={t.id}>
                    <TD className="font-medium text-ink">{t.name}</TD>
                    <TD className="text-right">{t.tax_percentage}%</TD>
                    <TD className="text-ink-muted">{t.description ?? "—"}</TD>
                    <TD><StatusBadge status={t.is_active ? "active" : "closed"} /></TD>
                    <TD className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => toggle.mutate(t)}>
                        {t.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New tax rule">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="space-y-1"><Label>Name</Label><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="space-y-1"><Label>Percentage</Label><Input required type="number" step="0.01" min="0" max="100" value={form.tax_percentage} onChange={(e) => setForm({ ...form, tax_percentage: e.target.value })} /></div>
          <div className="space-y-1"><Label>Description</Label><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
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
