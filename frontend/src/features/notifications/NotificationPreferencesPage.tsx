import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Bell } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import {
  getNotificationPreferences,
  saveNotificationPreferences,
  type NotificationPreferences,
} from "../../api/notifications";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";

const SECTIONS: {
  title: string;
  fields: { key: keyof NotificationPreferences; label: string }[];
}[] = [
  {
    title: "General",
    fields: [
      { key: "email_enabled", label: "Email notifications" },
      { key: "in_app_enabled", label: "In-app notifications" },
    ],
  },
  {
    title: "Payment notifications",
    fields: [
      { key: "payment_due_enabled", label: "Payment due reminders" },
      { key: "overdue_enabled", label: "Overdue payment notifications" },
      {
        key: "payment_confirmation_enabled",
        label: "Payment confirmations",
      },
    ],
  },
  {
    title: "Invoice notifications",
    fields: [
      { key: "invoice_due_enabled", label: "Upcoming invoice due reminders" },
      { key: "invoice_generated_enabled", label: "New invoices generated" },
    ],
  },
  {
    title: "Subscription notifications",
    fields: [{ key: "renewal_enabled", label: "Subscription renewals" }],
  },
];

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    return "Your session has expired. Sign in again to manage preferences.";
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

export default function NotificationPreferencesPage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: getNotificationPreferences,
  });
  const [values, setValues] = useState<NotificationPreferences | null>(null);
  useEffect(() => {
    if (query.data) {
      const {
        email_enabled,
        in_app_enabled,
        payment_due_enabled,
        invoice_due_enabled,
        overdue_enabled,
        renewal_enabled,
        payment_confirmation_enabled,
        invoice_generated_enabled,
      } = query.data;
      setValues({
        email_enabled,
        in_app_enabled,
        payment_due_enabled,
        invoice_due_enabled,
        overdue_enabled,
        renewal_enabled,
        payment_confirmation_enabled,
        invoice_generated_enabled,
      });
    }
  }, [query.data]);

  const save = useMutation({
    mutationFn: saveNotificationPreferences,
    onSuccess: async (data) => {
      setValues(data);
      await queryClient.invalidateQueries({
        queryKey: ["notification-preferences"],
      });
    },
  });

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Notification preferences
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Choose which updates you receive and where they are delivered.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Essential transaction confirmations may still be sent when required.
        </p>
      </div>

      {query.isLoading && (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading preferences…
        </p>
      )}
      {query.isError && (
        <div
          className="flex items-center gap-2 rounded-md bg-red-50 p-4 text-sm text-red-700"
          role="alert"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          {errorMessage(query.error)}
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => void query.refetch()}
          >
            Retry
          </Button>
        </div>
      )}
      {save.isError && (
        <p className="text-sm text-red-700" role="alert">
          Could not save preferences: {errorMessage(save.error)}
        </p>
      )}
      {save.isSuccess && (
        <p className="text-sm text-emerald-700" role="status">
          Preferences saved.
        </p>
      )}

      {values && (
        <>
          {SECTIONS.map((section) => (
            <Card key={section.title}>
              <CardHeader>
                <CardTitle>{section.title}</CardTitle>
              </CardHeader>
              <CardContent className="divide-y divide-slate-100">
                {section.fields.map(({ key, label }) => (
                  <label
                    className="flex cursor-pointer items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
                    key={key}
                  >
                    <span className="text-sm text-slate-700">{label}</span>
                    <input
                      type="checkbox"
                      role="switch"
                      className="h-4 w-4 accent-slate-900"
                      checked={values[key]}
                      onChange={(event) => {
                        setValues((current) =>
                          current
                            ? { ...current, [key]: event.target.checked }
                            : current,
                        );
                        save.reset();
                      }}
                    />
                  </label>
                ))}
              </CardContent>
            </Card>
          ))}
          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-xs text-slate-500">
              <Bell className="h-4 w-4" />
              Changes take effect after saving.
            </span>
            <Button
              disabled={save.isPending}
              onClick={() => {
                save.mutate(values);
              }}
            >
              {save.isPending ? "Saving…" : "Save preferences"}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
