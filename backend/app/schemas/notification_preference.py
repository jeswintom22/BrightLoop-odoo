import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_enabled: bool
    in_app_enabled: bool
    payment_due_enabled: bool
    invoice_due_enabled: bool
    overdue_enabled: bool
    renewal_enabled: bool
    payment_confirmation_enabled: bool
    invoice_generated_enabled: bool


class NotificationPreferenceResponse(NotificationPreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
