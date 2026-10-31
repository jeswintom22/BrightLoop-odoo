import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, qs } from "../../api/client";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import { PageHeader, TableSkeleton, Empty } from "../../components/ui/extras";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";

interface Customer { id: string; name: string; email: string; phone: string | null; billing_address: string | null }
interface Page<T> { items: T[]; total: number; page: number }

export default function CustomersPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const customers = useQuery({
    queryKey: ["customers", search, page],
    queryFn: () => api<Page<Customer>>(`/customers${qs({ search, page, page_size: 15 })}`),
  });

  return (
    <div>
      <PageHeader title="Customers" description="Customer accounts created at registration or by staff." />
      <Card>
        <CardContent className="pt-5">
          <div className="mb-4">
            <Input
              className="max-w-xs"
              placeholder="Search name or email…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          {customers.isLoading && <TableSkeleton />}
          {customers.data && customers.data.items.length === 0 && <Empty text="No customers found." />}
          {customers.data && customers.data.items.length > 0 && (
            <>
              <Table>
                <THead><TR><TH>Name</TH><TH>Email</TH><TH>Phone</TH><TH>Billing address</TH></TR></THead>
                <TBody>
                  {customers.data.items.map((c) => (
                    <TR key={c.id}>
                      <TD className="font-medium text-ink">{c.name}</TD>
                      <TD>{c.email}</TD>
                      <TD>{c.phone ?? "—"}</TD>
                      <TD className="text-ink-muted">{c.billing_address ?? "—"}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              <div className="mt-4 flex items-center justify-between text-sm text-ink-muted">
                <span>{customers.data.total} customers</span>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
                  <Button size="sm" variant="outline" disabled={customers.data.items.length < 15} onClick={() => setPage(page + 1)}>Next</Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
