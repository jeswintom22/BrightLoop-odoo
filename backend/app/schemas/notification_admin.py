import datetime as dt
import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

NotificationAdminType = Literal[
    "payment_due",
    "invoice_due",
    "payment_overdue",
    "subscription_renewal",
    "payment_confirmation",
    "invoice_generated",
]
DeliveryStatus = Literal["pending", "sent", "delivered", "failed", "cancelled"]


class ReminderRule(BaseModel):
    notification_type: Literal[
        "invoice_due", "payment_overdue", "subscription_renewal"
    ]
    days_offset: int = Field(ge=-365, le=365)
    is_active: bool = True

    @field_validator("days_offset")
    @classmethod
    def validate_nonzero_offset(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Reminder offset cannot be zero")
        return value


class ReminderRuleList(BaseModel):
    items: list[ReminderRule]


class CategorySetting(BaseModel):
    notification_type: NotificationAdminType
    is_enabled: bool


class CategorySettingList(BaseModel):
    items: list[CategorySetting]


class EmailTemplateUpdate(BaseModel):
    subject_template: str = Field(min_length=1, max_length=255)
    html_template: str = Field(min_length=1, max_length=50000)
    text_template: str = Field(min_length=1, max_length=20000)
    is_active: bool = True


class EmailTemplateOut(EmailTemplateUpdate):
    model_config = ConfigDict(from_attributes=True)

    notification_type: NotificationAdminType
    updated_by: uuid.UUID | None
    updated_at: dt.datetime


class NotificationHistoryItem(BaseModel):
    delivery_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None
    customer_email: str | None
    notification_type: NotificationAdminType
    channel: Literal["in_app", "email"]
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    created_at: dt.datetime
    sent_at: dt.datetime | None
    delivered_at: dt.datetime | None
    delivery_status: DeliveryStatus
    failure_reason: str | None
    attempt_count: int
    subject: str | None


class NotificationHistoryPage(BaseModel):
    items: list[NotificationHistoryItem]
    total: int
    page: int
    page_size: int


class NotificationStats(BaseModel):
    pending: int = 0
    sent: int = 0
    delivered: int = 0
    failed: int = 0
    cancelled: int = 0


class NotificationSenderSettings(BaseModel):
    sender_name: str = Field(min_length=1, max_length=128)
    sender_email: str = Field(min_length=3, max_length=320)

    @field_validator("sender_email")
    @classmethod
    def validate_sender_email(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("A valid sender email address is required")
        return value

    @field_validator("sender_name")
    @classmethod
    def validate_sender_name(cls, value: str) -> str:
        value = value.strip()
        if "\r" in value or "\n" in value:
            raise ValueError("Sender name cannot contain line breaks")
        if not value:
            raise ValueError("Sender name cannot be empty")
        return value


class NotificationSenderSettingsOut(NotificationSenderSettings):
    model_config = ConfigDict(from_attributes=True)

    updated_at: dt.datetime | None = None
