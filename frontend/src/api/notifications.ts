import { api, qs } from "./client";

export type NotificationType =
  | "payment_due"
  | "invoice_due"
  | "payment_overdue"
  | "subscription_renewal"
  | "payment_confirmation"
  | "invoice_generated";

export interface CustomerNotification {
  id: string;
  title: string;
  message: string;
  notification_type: NotificationType;
  channel: "in_app" | "email";
  related_entity_type: string | null;
  related_entity_id: string | null;
  status: "pending" | "sent" | "delivered" | "failed" | "read" | "cancelled";
  is_read: boolean;
  read_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationPage {
  items: CustomerNotification[];
  total: number;
  page: number;
  page_size: number;
}

export interface NotificationPreferences {
  email_enabled: boolean;
  in_app_enabled: boolean;
  payment_due_enabled: boolean;
  invoice_due_enabled: boolean;
  overdue_enabled: boolean;
  renewal_enabled: boolean;
  payment_confirmation_enabled: boolean;
  invoice_generated_enabled: boolean;
}

export interface NotificationPreferencesResponse extends NotificationPreferences {
  id: string;
  customer_id: string;
  created_at: string;
  updated_at: string;
}

export function getNotifications(params: {
  page: number;
  page_size: number;
  notification_type?: string;
  is_read?: boolean;
}) {
  return api<NotificationPage>(
    `/notifications${qs({
      page: params.page,
      page_size: params.page_size,
      notification_type: params.notification_type,
      is_read: params.is_read,
    })}`,
  );
}

export function getUnreadCount() {
  return api<{ unread_count: number }>("/notifications/unread-count");
}

export function markNotificationRead(id: string) {
  return api<CustomerNotification>(`/notifications/${id}/read`, {
    method: "PATCH",
  });
}

export function markAllNotificationsRead() {
  return api<{ updated_count: number }>("/notifications/read-all", {
    method: "PATCH",
  });
}

export function deleteNotification(id: string) {
  return api<void>(`/notifications/${id}`, { method: "DELETE" });
}

export function getNotificationPreferences() {
  return api<NotificationPreferencesResponse>("/notification-preferences");
}

export function saveNotificationPreferences(preferences: NotificationPreferences) {
  return api<NotificationPreferencesResponse>("/notification-preferences", {
    method: "PUT",
    body: JSON.stringify(preferences),
  });
}
