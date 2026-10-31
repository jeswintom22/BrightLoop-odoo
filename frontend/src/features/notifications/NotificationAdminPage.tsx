import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../../api/client";
import {
  getEmailTemplates,
  getNotificationCategories,
  getNotificationHistory,
  getNotificationStats,
  getReminderRules,
  getSenderSettings,
  retryNotificationDelivery,
  saveEmailTemplate,
  saveNotificationCategories,
  saveReminderRules,
  saveSenderSettings,
  type CategorySetting,
  type EmailTemplate,
  type NotificationHistoryItem,
  type ReminderRule,
  type ReminderType,
  type SenderSettings,
} from "../../api/notificationAdmin";
import type { NotificationType } from "../../api/notifications";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Select } from "../../components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "../../components/ui/table";

const TYPES: { value: NotificationType; label: string }[] = [
  { value: "invoice_due", label: "Invoice due" },
  { value: "payment_overdue", label: "Overdue invoice" },
  { value: "subscription_renewal", label: "Subscription renewal" },
  { value: "payment_confirmation", label: "Payment confirmation" },
  { value: "invoice_generated", label: "Invoice generated" },
  { value: "payment_due", label: "Payment due" },
];

const REMINDER_TYPES: { value: ReminderType; label: string }[] = [
  { value: "invoice_due", label: "Invoice due" },
  { value: "payment_overdue", label: "Overdue invoice" },
  { value: "subscription_renewal", label: "Subscription renewal" },
];

function message(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Something went wrong.";
}

function timestamp(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

function ReminderSection() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["notification-admin-rules"],
    queryFn: getReminderRules,
  });
  const [rules, setRules] = useState<ReminderRule[]>([]);
  const [newType, setNewType] = useState<ReminderType>("invoice_due");
  const [newOffset, setNewOffset] = useState("7");
  useEffect(() => {
    if (query.data) setRules(query.data.items);
  }, [query.data]);

  const save = useMutation({
    mutationFn: saveReminderRules,
    onSuccess: async (result) => {
      setRules(result.items);
      await qc.invalidateQueries({ queryKey: ["notification-admin-rules"] });
    },
  });
  const addRule = () => {
    const magnitude = Number(newOffset);
    if (!Number.isInteger(magnitude) || magnitude < 1 || magnitude > 365) return;
    const offset = newType === "payment_overdue" ? -magnitude : magnitude;
    if (rules.some((rule) => rule.notification_type === newType && rule.days_offset === offset)) {
      return;
    }
    setRules((current) => [
      ...current,
      { notification_type: newType, days_offset: offset, is_active: true },
    ]);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reminder schedules</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-slate-600">
          Positive offsets send before due dates or renewals; overdue offsets are
          days after an invoice due date.
        </p>
        {query.isError && <p role="alert" className="text-sm text-red-700">{message(query.error)}</p>}
        {save.isError && <p role="alert" className="text-sm text-red-700">{message(save.error)}</p>}
        <div className="space-y-2">
          {rules.map((rule) => (
            <label
              key={`${rule.notification_type}:${rule.days_offset}`}
              className="flex items-center justify-between gap-4 rounded-md border border-slate-200 p-3 text-sm"
            >
              <span>
                {REMINDER_TYPES.find((item) => item.value === rule.notification_type)?.label}
                {" · "}
                {Math.abs(rule.days_offset)} day{Math.abs(rule.days_offset) === 1 ? "" : "s"}
                {rule.days_offset < 0 ? " overdue" : " before"}
              </span>
              <input
                type="checkbox"
                checked={rule.is_active}
                aria-label={`Enable ${rule.notification_type} reminder ${rule.days_offset}`}
                onChange={(event) =>
                  setRules((current) =>
                    current.map((item) =>
                      item === rule ? { ...item, is_active: event.target.checked } : item,
                    ),
                  )
                }
              />
            </label>
          ))}
          {rules.length === 0 && !query.isLoading && (
            <p className="text-sm text-slate-500">No reminder intervals configured.</p>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-40 flex-1 space-y-1">
            <Label htmlFor="reminder-type">Reminder type</Label>
            <Select id="reminder-type" value={newType} onChange={(event) => setNewType(event.target.value as ReminderType)}>
              {REMINDER_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </Select>
          </div>
          <div className="w-28 space-y-1">
            <Label htmlFor="reminder-days">Days</Label>
            <Input id="reminder-days" type="number" min={1} max={365} value={newOffset} onChange={(event) => setNewOffset(event.target.value)} />
          </div>
          <Button type="button" variant="outline" onClick={addRule}>Add interval</Button>
          <Button disabled={save.isPending} onClick={() => save.mutate(rules)}>
            {save.isPending ? "Saving…" : "Save schedules"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function CategorySection() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["notification-admin-categories"],
    queryFn: getNotificationCategories,
  });
  const [items, setItems] = useState<CategorySetting[]>([]);
  useEffect(() => {
    if (query.data) setItems(query.data.items);
  }, [query.data]);
  const save = useMutation({
    mutationFn: saveNotificationCategories,
    onSuccess: async (data) => {
      setItems(data.items);
      await qc.invalidateQueries({ queryKey: ["notification-admin-categories"] });
    },
  });
  return (
    <Card>
      <CardHeader><CardTitle>Notification categories</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {query.isError && <p role="alert" className="text-sm text-red-700">{message(query.error)}</p>}
        {save.isError && <p role="alert" className="text-sm text-red-700">{message(save.error)}</p>}
        <div className="grid gap-2 sm:grid-cols-2">
          {items.map((item) => (
            <label key={item.notification_type} className="flex items-center justify-between gap-3 rounded-md border border-slate-200 p-3 text-sm">
              {TYPES.find((type) => type.value === item.notification_type)?.label ?? item.notification_type}
              <input
                type="checkbox"
                checked={item.is_enabled}
                onChange={(event) =>
                  setItems((current) =>
                    current.map((row) =>
                      row.notification_type === item.notification_type
                        ? { ...row, is_enabled: event.target.checked }
                        : row,
                    ),
                  )
                }
              />
            </label>
          ))}
        </div>
        <Button disabled={save.isPending} onClick={() => save.mutate(items)}>
          {save.isPending ? "Saving…" : "Save categories"}
        </Button>
      </CardContent>
    </Card>
  );
}

function SenderSection() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["notification-admin-sender"], queryFn: getSenderSettings });
  const [sender, setSender] = useState<SenderSettings | null>(null);
  useEffect(() => {
    if (query.data) setSender(query.data);
  }, [query.data]);
  const save = useMutation({
    mutationFn: saveSenderSettings,
    onSuccess: async (data) => {
      setSender(data);
      await qc.invalidateQueries({ queryKey: ["notification-admin-sender"] });
    },
  });
  return (
    <Card>
      <CardHeader><CardTitle>Email sender</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {query.isError && <p role="alert" className="text-sm text-red-700">{message(query.error)}</p>}
        {save.isError && <p role="alert" className="text-sm text-red-700">{message(save.error)}</p>}
        {sender && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1"><Label htmlFor="sender-name">Sender name</Label><Input id="sender-name" value={sender.sender_name} onChange={(event) => setSender({ ...sender, sender_name: event.target.value })} /></div>
            <div className="space-y-1"><Label htmlFor="sender-email">Sender email</Label><Input id="sender-email" type="email" value={sender.sender_email} onChange={(event) => setSender({ ...sender, sender_email: event.target.value })} /></div>
          </div>
        )}
        <Button disabled={!sender || save.isPending} onClick={() => sender && save.mutate(sender)}>
          {save.isPending ? "Saving…" : "Save sender"}
        </Button>
      </CardContent>
    </Card>
  );
}

function TemplateSection() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["notification-admin-templates"], queryFn: getEmailTemplates });
  const [selected, setSelected] = useState<NotificationType>("subscription_renewal");
  const template = useMemo(
    () => query.data?.find((item) => item.notification_type === selected),
    [query.data, selected],
  );
  const [draft, setDraft] = useState<EmailTemplate | null>(null);
  useEffect(() => setDraft(template ?? null), [template]);
  const save = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error("Choose a template first.");
      return saveEmailTemplate(selected, draft);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["notification-admin-templates"] });
    },
  });
  return (
    <Card>
      <CardHeader><CardTitle>Email templates</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {query.isError && <p role="alert" className="text-sm text-red-700">{message(query.error)}</p>}
        {save.isError && <p role="alert" className="text-sm text-red-700">{message(save.error)}</p>}
        <div className="max-w-sm space-y-1">
          <Label htmlFor="template-type">Template</Label>
          <Select id="template-type" value={selected} onChange={(event) => setSelected(event.target.value as NotificationType)}>
            {TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </Select>
        </div>
        {draft && (
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.is_active} onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })} />Template active</label>
            <div className="space-y-1"><Label htmlFor="template-subject">Subject</Label><Input id="template-subject" value={draft.subject_template} onChange={(event) => setDraft({ ...draft, subject_template: event.target.value })} /></div>
            <div className="space-y-1"><Label htmlFor="template-html">HTML body</Label><textarea id="template-html" className="min-h-48 w-full rounded-md border border-slate-300 p-3 font-mono text-xs" value={draft.html_template} onChange={(event) => setDraft({ ...draft, html_template: event.target.value })} /></div>
            <div className="space-y-1"><Label htmlFor="template-text">Text body</Label><textarea id="template-text" className="min-h-28 w-full rounded-md border border-slate-300 p-3 font-mono text-xs" value={draft.text_template} onChange={(event) => setDraft({ ...draft, text_template: event.target.value })} /></div>
            <p className="text-xs text-slate-500">Available placeholders vary by message, including {"{{customer_name}}"}, {"{{invoice_number}}"}, {"{{invoice_amount}}"}, {"{{due_date}}"}, {"{{subscription_name}}"}, {"{{renewal_date}}"} and {"{{transaction_id}}"}.</p>
            <Button disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save template"}</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HistorySection() {
  const qc = useQueryClient();
  const stats = useQuery({ queryKey: ["notification-admin-stats"], queryFn: getNotificationStats });
  const [filters, setFilters] = useState({ notification_type: "", customer_id: "", delivery_status: "", date_from: "", date_to: "" });
  const [applied, setApplied] = useState(filters);
  const [page, setPage] = useState(1);
  const history = useQuery({
    queryKey: ["notification-admin-history", applied, page],
    queryFn: () => getNotificationHistory(applied, page),
  });
  const retry = useMutation({
    mutationFn: retryNotificationDelivery,
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["notification-admin-history"] }),
        qc.invalidateQueries({ queryKey: ["notification-admin-stats"] }),
      ]);
    },
  });
  const updateFilter = (key: keyof typeof filters, value: string) =>
    setFilters((current) => ({ ...current, [key]: value }));

  return (
    <Card>
      <CardHeader><CardTitle>Delivery history</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {stats.data && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {Object.entries(stats.data).map(([status, count]) => (
              <div key={status} className="rounded-md bg-slate-50 p-3 text-center">
                <div className="text-xl font-semibold">{count}</div>
                <div className="text-xs capitalize text-slate-500">{status}</div>
              </div>
            ))}
          </div>
        )}
        {(history.isError || stats.isError) && <p role="alert" className="text-sm text-red-700">{message(history.error ?? stats.error)}</p>}
        {retry.isError && <p role="alert" className="text-sm text-red-700">{message(retry.error)}</p>}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Select aria-label="Notification type filter" value={filters.notification_type} onChange={(event) => updateFilter("notification_type", event.target.value)}>
            <option value="">All types</option>
            {TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </Select>
          <Input aria-label="Customer UUID filter" placeholder="Customer UUID" value={filters.customer_id} onChange={(event) => updateFilter("customer_id", event.target.value)} />
          <Select aria-label="Delivery status filter" value={filters.delivery_status} onChange={(event) => updateFilter("delivery_status", event.target.value)}>
            <option value="">All statuses</option>
            {["pending", "sent", "delivered", "failed", "cancelled"].map((status) => <option key={status} value={status}>{status}</option>)}
          </Select>
          <Input aria-label="Start date filter" type="date" value={filters.date_from} onChange={(event) => updateFilter("date_from", event.target.value)} />
          <Input aria-label="End date filter" type="date" value={filters.date_to} onChange={(event) => updateFilter("date_to", event.target.value)} />
        </div>
        <Button variant="outline" onClick={() => { setPage(1); setApplied(filters); }}>Apply filters</Button>
        <Table>
          <THead><TR><TH>Customer</TH><TH>Type</TH><TH>Channel</TH><TH>Related</TH><TH>Sent / delivery</TH><TH>Status</TH><TH>Failure</TH><TH /></TR></THead>
          <TBody>
            {history.data?.items.map((item: NotificationHistoryItem) => (
              <TR key={item.delivery_id}>
                <TD><div>{item.customer_name ?? item.customer_id.slice(0, 8)}</div><div className="text-xs text-slate-500">{item.customer_email ?? "—"}</div></TD>
                <TD>{TYPES.find((type) => type.value === item.notification_type)?.label ?? item.notification_type}</TD>
                <TD className="capitalize">{item.channel.replace("_", " ")}</TD>
                <TD>{item.related_entity_type ?? "—"}<div className="font-mono text-xs">{item.related_entity_id ?? ""}</div></TD>
                <TD>{timestamp(item.sent_at ?? item.created_at)}<div className="text-xs text-slate-500">{timestamp(item.delivered_at)}</div></TD>
                <TD className="capitalize">{item.delivery_status}</TD>
                <TD className="max-w-56 whitespace-normal text-xs text-red-700">{item.failure_reason ?? "—"}</TD>
                <TD>{item.delivery_status === "failed" && <Button size="sm" variant="outline" disabled={retry.isPending} onClick={() => retry.mutate(item.delivery_id)}>Retry</Button>}</TD>
              </TR>
            ))}
            {history.data?.items.length === 0 && <TR><TD colSpan={8} className="py-8 text-center text-slate-500">No notifications match these filters.</TD></TR>}
          </TBody>
        </Table>
        {history.data && history.data.total > history.data.page_size && (
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>
              Showing {(history.data.page - 1) * history.data.page_size + 1}–
              {Math.min(history.data.page * history.data.page_size, history.data.total)}
              {" of "}{history.data.total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</Button>
              <Button variant="outline" size="sm" disabled={page * history.data.page_size >= history.data.total} onClick={() => setPage((current) => current + 1)}>Next</Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function NotificationAdminPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Notification administration</h1>
        <p className="mt-1 text-sm text-slate-600">Manage notification schedules, templates, sender details, and delivery status.</p>
      </div>
      <ReminderSection />
      <CategorySection />
      <SenderSection />
      <TemplateSection />
      <HistorySection />
    </div>
  );
}
