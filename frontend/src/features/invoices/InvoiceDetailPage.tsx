import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";
import { api, ApiError } from "../../api/client";
import type {
  EmailResult,
  InvoiceDetail,
  Payment,
} from "../../api/types";
import { StatusBadge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Select } from "../../components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";
import { formatDate, formatMoney } from "../../lib/utils";

const METHODS = ["upi", "bank_transfer", "cash", "card", "other"] as const;

const paymentSchema = z.object({
  amount: z.coerce.number().positive("Amount must be positive"),
  method: z.enum(METHODS),
  paid_at: z.string().optional(),
  notes: z.string().optional(),
});
type PaymentForm = z.infer<typeof paymentSchema>;

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  // Stable per page-load — protects against double-submit/refresh retries.
  const idempotencyKey = useMemo(() => crypto.randomUUID(), []);

  const invoice = useQuery({
    queryKey: ["invoice", id],
    queryFn: () => api<InvoiceDetail>(`/invoices/${id}`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["invoice", id] });
    qc.invalidateQueries({ queryKey: ["invoices"] });
    qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const action = useMutation({
    mutationFn: (verb: "confirm" | "cancel") =>
      api<InvoiceDetail>(`/invoices/${id}/${verb}`, { method: "POST" }),
    onSuccess: invalidate,
  });

  const email = useMutation({
    mutationFn: () =>
      api<EmailResult>(`/invoices/${id}/email`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: invalidate,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PaymentForm>({
    resolver: zodResolver(paymentSchema),
    defaultValues: { method: "upi" },
  });

  const recordPayment = useMutation({
    mutationFn: (values: PaymentForm) =>
      api<Payment>("/payments", {
        method: "POST",
        body: JSON.stringify({
          invoice_id: id,
          amount: values.amount.toFixed(2),
          method: values.method,
          paid_at: values.paid_at
            ? new Date(values.paid_at).toISOString()
            : undefined,
          notes: values.notes || undefined,
          idempotency_key: idempotencyKey,
        }),
      }),
    onSuccess: () => {
      reset({ method: "upi" });
      invalidate();
    },
  });

  const inv = invoice.data;
  const paymentError =
    recordPayment.error instanceof ApiError
      ? `${recordPayment.error.code}: ${recordPayment.error.message}`
      : recordPayment.isError
        ? "Failed to record payment"
        : null;

  if (invoice.isLoading) return <p className="text-cream0">Loading…</p>;
  if (invoice.isError || !inv)
    return <p className="text-danger">Invoice not found.</p>;

  const canPay = inv.status === "confirmed";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/invoices" className="text-sm text-cream0 hover:underline">
            ← Invoices
          </Link>
          <h1 className="flex items-center gap-3 font-mono text-xl font-bold">
            {inv.invoice_number}
            <StatusBadge status={inv.status} />
          </h1>
          <p className="mt-1 text-sm text-cream0">
            {inv.customer_name ?? inv.customer_id} · issued{" "}
            {formatDate(inv.issue_date)} · due {formatDate(inv.due_date)} · period{" "}
            {formatDate(inv.period_start)} — {formatDate(inv.period_end)}
          </p>
        </div>
        <div className="flex gap-2">
          {inv.status === "draft" && (
            <Button
              onClick={() => action.mutate("confirm")}
              disabled={action.isPending}
            >
              Confirm
            </Button>
          )}
          {(inv.status === "draft" || inv.status === "confirmed") &&
            inv.amount_paid === 0 && (
              <Button
                variant="outline"
                onClick={() => action.mutate("cancel")}
                disabled={action.isPending}
              >
                Cancel
              </Button>
            )}
          <Button
            variant="outline"
            onClick={() => window.open(`/api/v1/invoices/${inv.id}/pdf`, "_blank")}
          >
            PDF
          </Button>
          <Button
            variant="outline"
            onClick={() => email.mutate()}
            disabled={email.isPending}
          >
            {email.isPending ? "Sending…" : "Email"}
          </Button>
        </div>
      </div>
      {email.data && (
        <p className="text-sm text-ink-muted">
          {email.data.sent
            ? "Invoice emailed."
            : `Email not sent (${email.data.reason ?? "unknown"}).`}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Lines</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Description</TH>
                <TH className="text-right">Qty</TH>
                <TH className="text-right">Unit</TH>
                <TH className="text-right">Tax</TH>
                <TH className="text-right">Total</TH>
              </TR>
            </THead>
            <TBody>
              {inv.lines.map((l) => (
                <TR key={l.id}>
                  <TD>{l.description}</TD>
                  <TD className="text-right">{l.quantity}</TD>
                  <TD className="text-right">{formatMoney(l.unit_price, inv.currency)}</TD>
                  <TD className="text-right">{formatMoney(l.tax_amount, inv.currency)}</TD>
                  <TD className="text-right">{formatMoney(l.line_total, inv.currency)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <div className="mt-4 ml-auto w-72 space-y-1 text-sm">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>{formatMoney(inv.subtotal, inv.currency)}</span>
            </div>
            <div className="flex justify-between">
              <span>Tax</span>
              <span>{formatMoney(inv.tax_total, inv.currency)}</span>
            </div>
            <div className="flex justify-between">
              <span>Discount</span>
              <span>-{formatMoney(inv.discount_total, inv.currency)}</span>
            </div>
            <div className="flex justify-between border-t pt-1 font-semibold">
              <span>Total</span>
              <span>{formatMoney(inv.total_amount, inv.currency)}</span>
            </div>
            <div className="flex justify-between text-ink-muted">
              <span>Paid</span>
              <span>{formatMoney(inv.amount_paid, inv.currency)}</span>
            </div>
            <div className="flex justify-between font-semibold">
              <span>Outstanding</span>
              <span>{formatMoney(inv.outstanding, inv.currency)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Payments</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <THead>
                <TR>
                  <TH>Reference</TH>
                  <TH>Method</TH>
                  <TH>Date</TH>
                  <TH>Status</TH>
                  <TH className="text-right">Amount</TH>
                </TR>
              </THead>
              <TBody>
                {inv.payments.map((p) => (
                  <TR key={p.id}>
                    <TD className="font-mono text-xs">{p.payment_reference}</TD>
                    <TD className="capitalize">{p.method.replace("_", " ")}</TD>
                    <TD>{formatDate(p.paid_at)}</TD>
                    <TD>
                      <StatusBadge status={p.status} />
                    </TD>
                    <TD className="text-right">{formatMoney(p.amount, inv.currency)}</TD>
                  </TR>
                ))}
                {inv.payments.length === 0 && (
                  <TR>
                    <TD colSpan={5} className="text-center text-cream0">
                      No payments recorded.
                    </TD>
                  </TR>
                )}
              </TBody>
            </Table>
          </CardContent>
        </Card>

        {canPay && (
          <Card>
            <CardHeader>
              <CardTitle>Record payment</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-3"
                onSubmit={handleSubmit((v) => recordPayment.mutate(v))}
              >
                <div>
                  <Label htmlFor="amount">Amount</Label>
                  <Input
                    id="amount"
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder={inv.outstanding.toFixed(2)}
                    {...register("amount")}
                  />
                  {errors.amount && (
                    <p className="mt-1 text-xs text-danger">
                      {errors.amount.message}
                    </p>
                  )}
                </div>
                <div>
                  <Label htmlFor="method">Method</Label>
                  <Select id="method" {...register("method")}>
                    {METHODS.map((m) => (
                      <option key={m} value={m}>
                        {m.replace("_", " ")}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label htmlFor="paid_at">Payment date</Label>
                  <Input id="paid_at" type="date" {...register("paid_at")} />
                </div>
                <div>
                  <Label htmlFor="notes">Notes</Label>
                  <Input id="notes" {...register("notes")} />
                </div>
                <Button type="submit" disabled={isSubmitting || recordPayment.isPending}>
                  {recordPayment.isPending ? "Recording…" : "Record payment"}
                </Button>
                {paymentError && (
                  <p className="text-sm text-danger">{paymentError}</p>
                )}
                {recordPayment.isSuccess && (
                  <p className="text-sm text-success">Payment recorded.</p>
                )}
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
