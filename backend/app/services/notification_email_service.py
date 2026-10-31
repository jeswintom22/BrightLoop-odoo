import html
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import resend
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_settings import (
    NotificationCategorySetting,
    NotificationDeliveryEvent,
    NotificationSenderSetting,
    NotificationTemplate,
)

logger = logging.getLogger("brightloop.notifications.email")
PLACEHOLDER = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")

DEFAULT_TEMPLATES = {
    "subscription_renewal": (
        "Subscription update: {{subscription_name}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1>Subscription update</h1><p>Hello {{customer_name}},</p><p><strong>{{subscription_name}}</strong> {{renewal_status}} on {{renewal_date}} for {{invoice_amount}}.</p><p>{{payment_instructions}}</p><p><a href='{{account_url}}'>View your account</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, {{subscription_name}} {{renewal_status}} on {{renewal_date}} for {{invoice_amount}}. {{payment_instructions}} {{account_url}}",
    ),
    "payment_confirmation": (
        "Payment received — {{transaction_id}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1>Payment confirmed</h1><p>Hello {{customer_name}},</p><p>We received {{invoice_amount}} on {{payment_date}}.</p><p>Transaction: {{transaction_id}} · Method: {{payment_method}}</p><p>Invoice {{invoice_number}}. Remaining balance: {{remaining_balance}}.</p><p><a href='{{invoice_url}}'>View invoice</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, payment {{transaction_id}} of {{invoice_amount}} was received on {{payment_date}} by {{payment_method}}. Invoice {{invoice_number}}. Remaining balance: {{remaining_balance}}. {{invoice_url}}",
    ),
    "invoice_generated": (
        "Invoice {{invoice_number}} is ready",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1>Your invoice is ready</h1><p>Hello {{customer_name}},</p><p>Invoice <strong>{{invoice_number}}</strong> dated {{invoice_date}} is {{payment_status}}.</p><p>Total: {{invoice_amount}} · Due: {{due_date}}</p><p>Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View or download invoice</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, invoice {{invoice_number}} dated {{invoice_date}} is {{payment_status}}. Total {{invoice_amount}}, due {{due_date}}, remaining {{remaining_balance}}. {{invoice_url}}",
    ),
    "invoice_due": (
        "Invoice {{invoice_number}} is due {{due_date}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1>Invoice payment reminder</h1><p>Hello {{customer_name}},</p><p>Invoice {{invoice_number}} is due on {{due_date}}.</p><p>Original total: {{invoice_amount}} · Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View invoice and payment options</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, invoice {{invoice_number}} is due {{due_date}}. Original total {{invoice_amount}}; remaining balance {{remaining_balance}}. {{invoice_url}}",
    ),
    "payment_overdue": (
        "Payment overdue: invoice {{invoice_number}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1>Overdue invoice notice</h1><p>Hello {{customer_name}},</p><p>Invoice {{invoice_number}} was due {{due_date}}.</p><p>Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View invoice and payment options</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, invoice {{invoice_number}} was due {{due_date}}. Remaining balance {{remaining_balance}}. {{invoice_url}}",
    ),
    "payment_due": (
        "Payment due: invoice {{invoice_number}}",
        "<!doctype html><html><body style='margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a'><table role='presentation' width='100%'><tr><td align='center' style='padding:32px 12px'><table role='presentation' width='600' style='max-width:600px;background:#fff;border-radius:12px;padding:32px'><tr><td><h1>Payment due reminder</h1><p>Hello {{customer_name}},</p><p>Invoice {{invoice_number}} is due {{due_date}}.</p><p>Remaining balance: {{remaining_balance}}</p><p><a href='{{invoice_url}}'>View invoice</a></p></td></tr></table></td></tr></table></body></html>",
        "Hello {{customer_name}}, payment for invoice {{invoice_number}} is due {{due_date}}. Remaining balance {{remaining_balance}}. {{invoice_url}}",
    ),
}


def _render(template: str, values: dict[str, str], *, escape_values: bool) -> str:
    def replace(match: re.Match[str]) -> str:
        value = values.get(match.group(1), "")
        return html.escape(value, quote=True) if escape_values else value

    return PLACEHOLDER.sub(replace, template)


class NotificationEmailService:
    @staticmethod
    def category_enabled(db: Session, notification_type: str) -> bool:
        setting = db.scalar(
            select(NotificationCategorySetting).where(
                NotificationCategorySetting.notification_type == notification_type
            )
        )
        return setting.is_enabled if setting is not None else True

    @staticmethod
    def render(
        db: Session, notification_type: str, values: dict[str, str]
    ) -> tuple[str, str, str]:
        template = db.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.notification_type == notification_type,
                NotificationTemplate.is_active.is_(True),
            )
        )
        if template is None:
            subject, html_template, text_template = DEFAULT_TEMPLATES[notification_type]
        else:
            subject = template.subject_template
            html_template = template.html_template
            text_template = template.text_template
        rendered_subject = _render(subject, values, escape_values=False)
        return (
            rendered_subject.replace("\r", "").replace("\n", ""),
            _render(html_template, values, escape_values=True),
            _render(text_template, values, escape_values=False),
        )

    @staticmethod
    def send(
        settings: Settings,
        delivery: NotificationDelivery,
        *,
        sender: Optional[str] = None,
        attachments: Optional[list[dict[str, str]]] = None,
    ) -> str:
        if (
            settings.ENVIRONMENT.lower() in {"prod", "production"}
            and settings.USE_STUB_PROVIDERS
        ):
            raise RuntimeError(
                "Email delivery is disabled while production uses stub providers"
            )
        if not settings.RESEND_API_KEY:
            raise RuntimeError("Email delivery is not configured (RESEND_API_KEY is empty)")
        if not delivery.recipient_email or not delivery.subject:
            raise RuntimeError("Email delivery is missing a recipient or rendered subject")

        resend.api_key = settings.RESEND_API_KEY
        params: dict = {
            "from": sender or settings.RESEND_FROM,
            "to": [delivery.recipient_email],
            "subject": delivery.subject,
            "html": delivery.html_body or "",
            "text": delivery.text_body or "",
        }
        if attachments:
            params["attachments"] = attachments
        response = resend.Emails.send(
            params, options={"idempotency_key": str(delivery.id)}
        )
        provider_id = getattr(response, "id", None)
        if not provider_id:
            raise RuntimeError("Email provider response did not include a message ID")
        return str(provider_id)

    @staticmethod
    def apply_webhook(
        db: Session,
        *,
        raw_body: str,
        event_id: str,
        timestamp: str,
        signature: str,
        webhook_secret: str,
    ) -> bool:
        event = resend.Webhooks.verify(
            {
                "payload": raw_body,
                "headers": {
                    "id": event_id,
                    "timestamp": timestamp,
                    "signature": signature,
                },
                "webhook_secret": webhook_secret,
            }
        )
        payload = event.model_dump() if hasattr(event, "model_dump") else event
        event_type = payload.get("type", "")
        data = payload.get("data") or {}
        provider_id = data.get("email_id") or data.get("id")
        if not provider_id:
            logger.warning("Ignoring verified Resend webhook without an email ID")
            return False

        delivery = db.scalar(
            select(NotificationDelivery)
            .where(NotificationDelivery.provider_message_id == provider_id)
            .with_for_update()
        )
        if delivery is None:
            logger.info("Ignoring Resend webhook for unknown message %s", provider_id)
            return False
        if delivery.provider_event_id == event_id:
            return True
        if db.scalar(
            select(NotificationDeliveryEvent).where(
                NotificationDeliveryEvent.provider_event_id == event_id
            )
        ):
            return True

        db.add(
            NotificationDeliveryEvent(
                delivery_id=delivery.id,
                provider_event_id=event_id,
                event_type=event_type,
            )
        )
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            if db.scalar(
                select(NotificationDeliveryEvent).where(
                    NotificationDeliveryEvent.provider_event_id == event_id
                )
            ):
                logger.info("Ignoring replayed Resend webhook event %s", event_id)
                return True
            raise

        if event_type == "email.delivered":
            delivery.delivery_status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
        elif event_type in {"email.bounced", "email.failed", "email.suppressed"}:
            if delivery.delivery_status not in {"delivered", "cancelled"}:
                delivery.delivery_status = "failed"
                delivery.failed_at = datetime.now(timezone.utc)
                delivery.error_message = str(data.get("reason") or event_type)[:4000]
                delivery.next_retry_at = None
        elif event_type in {"email.sent", "email.delivery_delayed"}:
            if delivery.delivery_status == "pending":
                delivery.delivery_status = "sent"
        else:
            db.rollback()
            logger.info("Ignoring unsupported Resend webhook event %s", event_type)
            return False

        delivery.provider_event_id = event_id
        notification = db.get(Notification, delivery.notification_id)
        if notification is not None:
            notification.status = (
                "delivered"
                if delivery.delivery_status == "delivered"
                else "failed"
                if delivery.delivery_status == "failed"
                else notification.status
            )
        db.commit()
        return True


def retry_at(now: datetime, attempt_count: int, delay_minutes: int) -> datetime:
    return now + timedelta(minutes=delay_minutes * (2 ** max(0, attempt_count - 1)))
