import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.deps import (
    CurrentUser,
    get_customer_provider,
    get_db,
    get_settings,
    require_roles,
)
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_settings import (
    NotificationCategorySetting,
    NotificationReminderRule,
    NotificationSenderSetting,
    NotificationTemplate,
)
from app.schemas.notification_admin import (
    CategorySetting,
    CategorySettingList,
    DeliveryStatus,
    EmailTemplateOut,
    EmailTemplateUpdate,
    NotificationHistoryItem,
    NotificationHistoryPage,
    NotificationStats,
    NotificationAdminType,
    ReminderRule,
    ReminderRuleList,
    NotificationSenderSettings,
    NotificationSenderSettingsOut,
)
from app.services.notification_delivery_service import NotificationDeliveryService
from app.services.notification_email_service import DEFAULT_TEMPLATES
from app.modules.billing.integrations import CustomerProvider

router = APIRouter(
    prefix="/admin/notifications",
    tags=["Admin Notifications"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("/rules", response_model=ReminderRuleList)
def list_reminder_rules(db: Session = Depends(get_db)):
    rules = db.scalars(
        select(NotificationReminderRule).order_by(
            NotificationReminderRule.notification_type,
            NotificationReminderRule.days_offset,
        )
    ).all()
    return ReminderRuleList(
        items=[
            ReminderRule.model_validate(rule, from_attributes=True) for rule in rules
        ]
    )


@router.put("/rules", response_model=ReminderRuleList)
def update_reminder_rules(
    body: ReminderRuleList,
    db: Session = Depends(get_db),
):
    seen: set[tuple[str, int]] = set()
    for item in body.items:
        key = (item.notification_type, item.days_offset)
        if key in seen:
            raise AppError("DUPLICATE_REMINDER_RULE", "Reminder rule is duplicated", 422)
        seen.add(key)
        if (
            item.notification_type in {"invoice_due", "subscription_renewal"}
            and item.days_offset < 0
        ) or (item.notification_type == "payment_overdue" and item.days_offset > 0):
            raise AppError(
                "INVALID_REMINDER_OFFSET",
                "Due and renewal offsets must be positive; overdue offsets must be negative",
                422,
            )
        rule = db.scalar(
            select(NotificationReminderRule).where(
                NotificationReminderRule.notification_type == item.notification_type,
                NotificationReminderRule.days_offset == item.days_offset,
            )
        )
        if rule is None:
            db.add(
                NotificationReminderRule(
                    notification_type=item.notification_type,
                    days_offset=item.days_offset,
                    is_active=item.is_active,
                )
            )
        else:
            rule.is_active = item.is_active
    db.commit()
    return list_reminder_rules(db)


@router.get("/categories", response_model=CategorySettingList)
def list_categories(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(NotificationCategorySetting).order_by(
            NotificationCategorySetting.notification_type
        )
    ).all()
    return CategorySettingList(
        items=[
            CategorySetting.model_validate(row, from_attributes=True) for row in rows
        ]
    )


@router.put("/categories", response_model=CategorySettingList)
def update_categories(
    body: CategorySettingList,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("admin")),
):
    types = [item.notification_type for item in body.items]
    if len(types) != len(set(types)):
        raise AppError("DUPLICATE_CATEGORY", "Notification category is duplicated", 422)
    for item in body.items:
        setting = db.scalar(
            select(NotificationCategorySetting).where(
                NotificationCategorySetting.notification_type == item.notification_type
            )
        )
        if setting is None:
            setting = NotificationCategorySetting(
                notification_type=item.notification_type,
                is_enabled=item.is_enabled,
            )
            db.add(setting)
        else:
            setting.is_enabled = item.is_enabled
        setting.updated_by = user.id
    db.commit()
    return list_categories(db)


@router.get("/templates", response_model=list[EmailTemplateOut])
def list_templates(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(NotificationTemplate).order_by(NotificationTemplate.notification_type)
    ).all()
    return rows


@router.get("/sender", response_model=NotificationSenderSettingsOut)
def get_sender_settings(
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
):
    row = db.get(NotificationSenderSetting, 1)
    if row is not None:
        return row
    sender_name, sender_email = settings.RESEND_FROM, ""
    if "<" in sender_name and sender_name.endswith(">"):
        sender_name, sender_email = sender_name.rsplit("<", 1)
        sender_name = sender_name.strip()
        sender_email = sender_email[:-1].strip()
    return NotificationSenderSettingsOut(
        sender_name=sender_name or "Brightloop Billing",
        sender_email=sender_email or "billing@brightloop.example",
        updated_at=None,
    )


@router.put("/sender", response_model=NotificationSenderSettingsOut)
def update_sender_settings(
    body: NotificationSenderSettings,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("admin")),
):
    row = db.get(NotificationSenderSetting, 1)
    if row is None:
        row = NotificationSenderSetting(id=1, **body.model_dump())
        db.add(row)
    else:
        row.sender_name = body.sender_name
        row.sender_email = body.sender_email
    row.updated_by = user.id
    db.commit()
    db.refresh(row)
    return row


@router.put("/templates/{notification_type}", response_model=EmailTemplateOut)
def update_template(
    notification_type: str,
    body: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("admin")),
):
    if notification_type not in DEFAULT_TEMPLATES:
        raise AppError("INVALID_NOTIFICATION_TYPE", "Unknown template type", 404)
    template = db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.notification_type == notification_type
        )
    )
    if template is None:
        default_subject, default_html, default_text = DEFAULT_TEMPLATES[
            notification_type
        ]
        template = NotificationTemplate(
            notification_type=notification_type,
            subject_template=default_subject,
            html_template=default_html,
            text_template=default_text,
        )
        db.add(template)
    for key, value in body.model_dump().items():
        setattr(template, key, value)
    template.updated_by = user.id
    db.commit()
    db.refresh(template)
    return template


@router.get("/history", response_model=NotificationHistoryPage)
def notification_history(
    notification_type: NotificationAdminType | None = None,
    customer_id: uuid.UUID | None = None,
    delivery_status: DeliveryStatus | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    customers: CustomerProvider = Depends(get_customer_provider),
):
    statement = select(NotificationDelivery, Notification).join(
        Notification, Notification.id == NotificationDelivery.notification_id
    )
    count_statement = (
        select(func.count())
        .select_from(NotificationDelivery)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
    )
    filters = []
    if notification_type:
        filters.append(Notification.notification_type == notification_type)
    if customer_id:
        filters.append(Notification.customer_id == customer_id)
    if delivery_status:
        filters.append(NotificationDelivery.delivery_status == delivery_status)
    if date_from:
        filters.append(
            NotificationDelivery.created_at
            >= dt.datetime.combine(date_from, dt.time.min, dt.timezone.utc)
        )
    if date_to:
        filters.append(
            NotificationDelivery.created_at
            < dt.datetime.combine(
                date_to + dt.timedelta(days=1), dt.time.min, dt.timezone.utc
            )
        )
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)
    total = db.scalar(count_statement) or 0
    rows = db.execute(
        statement.order_by(NotificationDelivery.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    names = customers.get_many([notification.customer_id for _, notification in rows])
    items = []
    for delivery, notification in rows:
        customer = names.get(notification.customer_id)
        items.append(
            NotificationHistoryItem(
                delivery_id=delivery.id,
                customer_id=notification.customer_id,
                customer_name=customer.name if customer else None,
                customer_email=customer.email if customer else delivery.recipient_email,
                notification_type=notification.notification_type,
                channel=delivery.channel,
                related_entity_type=notification.related_entity_type,
                related_entity_id=notification.related_entity_id,
                created_at=delivery.created_at,
                sent_at=delivery.sent_at,
                delivered_at=delivery.delivered_at,
                delivery_status=delivery.delivery_status,
                failure_reason=delivery.error_message,
                attempt_count=delivery.attempt_count,
                subject=delivery.subject,
            )
        )
    return NotificationHistoryPage(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/stats", response_model=NotificationStats)
def notification_stats(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(
                NotificationDelivery.delivery_status,
                func.count(NotificationDelivery.id),
            ).group_by(NotificationDelivery.delivery_status)
        ).all()
    )
    return NotificationStats(**counts)


@router.post("/deliveries/{delivery_id}/retry")
def retry_delivery(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
):
    try:
        delivery = NotificationDeliveryService.retry_failed(
            db, delivery_id, settings
        )
    except LookupError as exc:
        raise AppError("DELIVERY_NOT_FOUND", "Notification delivery not found", 404) from exc
    except ValueError as exc:
        raise AppError("DELIVERY_NOT_RETRYABLE", str(exc), 409) from exc
    return {
        "delivery_id": delivery.id,
        "delivery_status": delivery.delivery_status,
        "attempt_count": delivery.attempt_count,
    }
