import { api, qs } from "./client";
import type { NotificationType } from "./notifications";

export type ReminderType =
  | "invoice_due"
  | "payment_overdue"
  | "subscription_renewal";

export interface ReminderRule {
  notification_type: ReminderType;
  days_offset: number;
  is_active: boolean;
}

export interface CategorySetting {
  notification_type: NotificationType;
  channel: "in_app" | "email";
  is_enabled: boolean;
}

export interface EmailTemplate {
  notification_type: NotificationType;
  subject_template: string;
  html_template: string;
  text_template: string;
  is_active: boolean;
  updated_by: string | null;
  updated_at: string;
}

export interface SenderSettings {
  sender_name: string;
  sender_email: string;
  updated_at?: string | null;
}

export type DeliveryStatus =
  | "pending"
  | "sent"
  | "delivered"
  | "failed"
  | "cancelled";

export interface NotificationHistoryItem {
  delivery_id: string;
  customer_id: string;
  customer_name: string | null;
  customer_email: string | null;
  notification_type: NotificationType;
  channel: "in_app" | "email";
  related_entity_type: string | null;
  related_entity_id: string | null;
  created_at: string;
  sent_at: string | null;
  delivered_at: string | null;
  delivery_status: DeliveryStatus;
  failure_reason: string | null;
  attempt_count: number;
  subject: string | null;
}

export interface NotificationHistoryPage {
  items: NotificationHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface NotificationStats {
  pending: number;
  sent: number;
  delivered: number;
  failed: number;
  cancelled: number;
}

export const getReminderRules = () =>
  api<{ items: ReminderRule[] }>("/admin/notifications/rules");

export const saveReminderRules = (items: ReminderRule[]) =>
  api<{ items: ReminderRule[] }>("/admin/notifications/rules", {
    method: "PUT",
    body: JSON.stringify({ items }),
  });

export const getNotificationCategories = () =>
  api<{ items: CategorySetting[] }>("/admin/notifications/categories");

export const saveNotificationCategories = (items: CategorySetting[]) =>
  api<{ items: CategorySetting[] }>("/admin/notifications/categories", {
    method: "PUT",
    body: JSON.stringify({ items }),
  });

export const getEmailTemplates = () =>
  api<EmailTemplate[]>("/admin/notifications/templates");

export const saveEmailTemplate = (
  type: NotificationType,
  template: Pick<
    EmailTemplate,
    "subject_template" | "html_template" | "text_template" | "is_active"
  >,
) =>
  api<EmailTemplate>(`/admin/notifications/templates/${type}`, {
    method: "PUT",
    body: JSON.stringify(template),
  });

export const getSenderSettings = () =>
  api<SenderSettings>("/admin/notifications/sender");

export const saveSenderSettings = (settings: SenderSettings) =>
  api<SenderSettings>("/admin/notifications/sender", {
    method: "PUT",
    body: JSON.stringify(settings),
  });

export const getNotificationHistory = (filters: {
  notification_type?: string;
  customer_id?: string;
  delivery_status?: string;
  date_from?: string;
  date_to?: string;
}, page = 1) =>
  api<NotificationHistoryPage>(
    `/admin/notifications/history${qs({ ...filters, page, page_size: 100 })}`,
  );

export const getNotificationStats = () =>
  api<NotificationStats>("/admin/notifications/stats");

export const retryNotificationDelivery = (id: string) =>
  api<{ delivery_id: string; delivery_status: DeliveryStatus; attempt_count: number }>(
    `/admin/notifications/deliveries/${id}/retry`,
    { method: "POST" },
  );
