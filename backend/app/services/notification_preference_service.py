import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.notification_preference import NotificationPreference
from app.schemas.notification_preference import NotificationPreferenceUpdate

CHANNEL_FIELDS = {"email": "email_enabled", "in_app": "in_app_enabled"}
CATEGORY_FIELDS = {
    "payment_due": "payment_due_enabled",
    "invoice_due": "invoice_due_enabled",
    "payment_overdue": "overdue_enabled",
    "subscription_renewal": "renewal_enabled",
    "payment_confirmation": "payment_confirmation_enabled",
    "invoice_generated": "invoice_generated_enabled",
}


class NotificationPreferenceService:
    @staticmethod
    def get_or_create(
        db: Session, customer_id: uuid.UUID, *, commit: bool = True
    ) -> NotificationPreference:
        preference = db.scalar(
            select(NotificationPreference).where(
                NotificationPreference.customer_id == customer_id
            )
        )
        if preference is not None:
            return preference

        preference = NotificationPreference(customer_id=customer_id)
        db.add(preference)
        try:
            db.flush()
            if commit:
                db.commit()
        except IntegrityError:
            db.rollback()
            preference = db.scalar(
                select(NotificationPreference).where(
                    NotificationPreference.customer_id == customer_id
                )
            )
            if preference is None:
                raise
            return preference
        if commit:
            db.refresh(preference)
        return preference

    @staticmethod
    def update(
        db: Session,
        customer_id: uuid.UUID,
        update_data: NotificationPreferenceUpdate,
    ) -> NotificationPreference:
        preference = NotificationPreferenceService.get_or_create(db, customer_id)
        for field, value in update_data.model_dump().items():
            setattr(preference, field, value)
        db.commit()
        db.refresh(preference)
        return preference

    @staticmethod
    def should_send_notification(
        db: Session,
        customer_id: uuid.UUID,
        notification_type: str,
        channel: str,
        *,
        commit_preference: bool = True,
    ) -> bool:
        channel_field = CHANNEL_FIELDS.get(channel)
        category_field = CATEGORY_FIELDS.get(notification_type)
        if channel_field is None or category_field is None:
            raise AppError(
                "INVALID_NOTIFICATION_SETTING",
                "Unsupported notification type or channel",
                400,
            )
        preference = NotificationPreferenceService.get_or_create(
            db, customer_id, commit=commit_preference
        )
        return bool(
            getattr(preference, channel_field)
            and getattr(preference, category_field)
        )


def should_send_notification(
    db: Session,
    customer_id: uuid.UUID,
    notification_type: str,
    channel: str,
) -> bool:
    return NotificationPreferenceService.should_send_notification(
        db, customer_id, notification_type, channel
    )
