import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, qs } from "../../api/client";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Select } from "../../components/ui/select";
import { Badge } from "../../components/ui/badge";
import { Modal, PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { useToast } from "../../components/ui/toast";

interface User { id: string; email: string; full_name: string; role: string; is_active: boolean }
interface Page<T> { items: T[]; total: number; page: number }
interface Me { role: string }

export default function StaffPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "staff" });
  const [error, setError] = useState<string | null>(null);

  const meQ = useQuery({ queryKey: ["me-role"], queryFn: () => api<Me>("/auth/me") });
  const isAdmin = meQ.data?.role === "admin";

  const users = useQuery({
    queryKey: ["users", page],
    queryFn: () => api<Page<User>>(`/users${qs({ page, page_size: 15 })}`),
  });

  const create = useMutation({
    mutationFn: () =>
      api<User>("/users/staff", { method: "POST", body: JSON.stringify(form) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setOpen(false); setForm({ email: "", full_name: "", password: "", role: "staff" });
      setError(null);
      toast("success", "Staff account created");
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Failed"),
  });

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const staff = users.data?.items.filter((u) => u.role === "admin" || u.role === "staff") ?? [];

  return (
    <div>
      <PageHeader
        title="Staff"
        description="Internal staff and administrator accounts."
        actions={isAdmin ? <Button onClick={() => setOpen(true)}>New staff account</Button> : undefined}
      />
      <Card>
        <CardContent className="pt-5">
          {users.isLoading && <TableSkeleton />}
          {staff.length === 0 && users.data && <Empty text="No staff accounts." />}
          {staff.length > 0 && (
            <>
              <Table>
                <THead><TR><TH>Name</TH><TH>Email</TH><TH>Role</TH><TH>Status</TH></TR></THead>
                <TBody>
                  {staff.map((u) => (
                    <TR key={u.id}>
                      <TD className="font-medium text-ink">{u.full_name}</TD>
                      <TD>{u.email}</TD>
                      <TD><Badge>{u.role}</Badge></TD>
                      <TD>{u.is_active ? "Active" : "Disabled"}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
                <span>{users.data?.total} users</span>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                  <Button size="sm" variant="outline" disabled={(users.data?.items.length ?? 0) < 15} onClick={() => setPage(page + 1)}>Next</Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Modal open={open} onClose={() => setOpen(false)} title="New staff account">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="space-y-1"><Label>Full name</Label><Input required value={form.full_name} onChange={set("full_name")} /></div>
          <div className="space-y-1"><Label>Email</Label><Input required type="email" value={form.email} onChange={set("email")} /></div>
          <div className="space-y-1"><Label>Temporary password</Label><Input required type="password" value={form.password} onChange={set("password")} /></div>
          <div className="space-y-1">
            <Label>Role</Label>
            <Select value={form.role} onChange={set("role")}>
              <option value="staff">Staff</option>
              <option value="admin">Admin</option>
            </Select>
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
