import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

NotificationType = Literal[
    "payment_due",
    "invoice_due",
    "payment_overdue",
    "subscription_renewal",
    "payment_confirmation",
    "invoice_generated",
]
NotificationChannel = Literal["in_app", "email"]
NotificationStatus = Literal[
    "pending", "sent", "delivered", "failed", "read", "cancelled"
]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    message: str
    notification_type: NotificationType
    channel: NotificationChannel
    related_entity_type: Optional[str]
    related_entity_id: Optional[uuid.UUID]
    status: NotificationStatus
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    unread_count: int = Field(ge=0)
