import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertCircle,
  Bell,
  Check,
  CircleAlert,
  CreditCard,
  FileText,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { ApiError } from "../../api/client";
import {
  deleteNotification,
  getNotifications,
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationType,
} from "../../api/notifications";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader } from "../../components/ui/card";
import { Label } from "../../components/ui/label";
import { Select } from "../../components/ui/select";
import { formatDateTime } from "../../lib/utils";

const PAGE_SIZE = 10;

const TYPE_LABELS: Record<NotificationType, string> = {
  payment_due: "Payment due",
  invoice_due: "Invoice due",
  payment_overdue: "Overdue payment",
  subscription_renewal: "Subscription renewal",
  payment_confirmation: "Payment confirmation",
  invoice_generated: "Invoice generated",
};

const TYPE_ICONS = {
  payment_due: CreditCard,
  invoice_due: FileText,
  payment_overdue: CircleAlert,
  subscription_renewal: RefreshCw,
  payment_confirmation: Check,
  invoice_generated: FileText,
} satisfies Record<NotificationType, typeof Bell>;

function errorText(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    return "Your session has expired. Sign in again to view notifications.";
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

export default function NotificationCenterPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [type, setType] = useState("");
  const [readFilter, setReadFilter] = useState("");
  const [feedback, setFeedback] = useState("");

  const query = useQuery({
    queryKey: ["notifications", page, type, readFilter],
    queryFn: () =>
      getNotifications({
        page,
        page_size: PAGE_SIZE,
        notification_type: type || undefined,
        is_read: readFilter === "" ? undefined : readFilter === "read",
      }),
  });
  const unread = useQuery({
    queryKey: ["notification-unread-count"],
    queryFn: getUnreadCount,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    void queryClient.invalidateQueries({
      queryKey: ["notification-unread-count"],
    });
  };
  const markRead = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      setFeedback("Notification marked as read.");
      refresh();
    },
  });
  const markAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: (result) => {
      setFeedback(`${result.updated_count} notification(s) marked as read.`);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: deleteNotification,
    onSuccess: () => {
      setFeedback("Notification deleted.");
      refresh();
    },
  });

  const totalPages = Math.max(
    1,
    Math.ceil((query.data?.total ?? 0) / PAGE_SIZE),
  );
  const mutationError = markRead.error ?? markAll.error ?? remove.error;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
          <p className="mt-1 text-sm text-slate-600">
            You have {unread.data?.unread_count ?? 0} unread notification(s).
          </p>
        </div>
        <Button
          variant="outline"
          disabled={!unread.data?.unread_count || markAll.isPending}
          onClick={() => {
            setFeedback("");
            markAll.mutate();
          }}
        >
          <Check className="h-4 w-4" />
          {markAll.isPending ? "Marking…" : "Mark all as read"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap gap-4">
            <div className="w-full sm:w-56">
              <Label htmlFor="notification-type">Notification type</Label>
              <Select
                id="notification-type"
                value={type}
                onChange={(event) => {
                  setType(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All types</option>
                {Object.entries(TYPE_LABELS).map(([key, label]) => (
                  <option value={key} key={key}>
                    {label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-full sm:w-44">
              <Label htmlFor="notification-read">Read status</Label>
              <Select
                id="notification-read"
                value={readFilter}
                onChange={(event) => {
                  setReadFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All</option>
                <option value="unread">Unread</option>
                <option value="read">Read</option>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {query.isLoading && (
            <div className="py-12 text-center text-sm text-slate-500">
              Loading notifications…
            </div>
          )}
          {query.isError && (
            <div
              className="flex items-center gap-2 rounded-md bg-red-50 p-4 text-sm text-red-700"
              role="alert"
            >
              <AlertCircle className="h-4 w-4 shrink-0" />
              {errorText(query.error)}
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
          {mutationError && (
            <p className="mb-3 text-sm text-red-700" role="alert">
              {errorText(mutationError)}
            </p>
          )}
          {feedback && (
            <p className="mb-3 text-sm text-emerald-700" role="status">
              {feedback}
            </p>
          )}
          {!query.isLoading && !query.isError && query.data?.items.length === 0 && (
            <div className="py-12 text-center">
              <Bell className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 font-medium">You’re all caught up</p>
              <p className="mt-1 text-sm text-slate-500">
                New account updates will appear here.
              </p>
            </div>
          )}
          <ul className="space-y-3">
            {query.data?.items.map((notification) => {
              const Icon = TYPE_ICONS[notification.notification_type];
              return (
                <li
                  key={notification.id}
                  className={`rounded-lg border p-4 ${
                    notification.is_read
                      ? "border-slate-200 bg-white"
                      : "border-blue-200 bg-blue-50/60"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 rounded-full bg-white p-2 text-slate-600">
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="font-semibold">{notification.title}</h2>
                        <Badge variant="secondary">
                          {TYPE_LABELS[notification.notification_type]}
                        </Badge>
                        {!notification.is_read && (
                          <Badge variant="default">Unread</Badge>
                        )}
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">
                        {notification.message}
                      </p>
                      <time
                        className="mt-2 block text-xs text-slate-500"
                        dateTime={notification.created_at}
                      >
                        {formatDateTime(notification.created_at)}
                      </time>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      {!notification.is_read && (
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Mark ${notification.title} as read`}
                          disabled={markRead.isPending}
                          onClick={() => {
                            setFeedback("");
                            markRead.mutate(notification.id);
                          }}
                        >
                          <Check className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Delete ${notification.title}`}
                        disabled={remove.isPending}
                        onClick={() => {
                          setFeedback("");
                          remove.mutate(notification.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
          {!!query.data?.total && (
            <div className="mt-4 flex items-center justify-between gap-3 text-sm text-slate-600">
              <span>
                {query.data.total} notification(s) · page {page} of {totalPages}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((value) => value - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
