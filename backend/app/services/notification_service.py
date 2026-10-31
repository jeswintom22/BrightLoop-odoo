import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.notification import Notification


class NotificationService:
    @staticmethod
    def list_notifications(
        db: Session,
        customer_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        notification_type: Optional[str] = None,
        is_read: Optional[bool] = None,
    ) -> tuple[list[Notification], int]:
        filters = [Notification.customer_id == customer_id]
        if notification_type is not None:
            filters.append(Notification.notification_type == notification_type)
        if is_read is not None:
            filters.append(Notification.is_read.is_(is_read))

        total = db.scalar(
            select(func.count()).select_from(Notification).where(*filters)
        ) or 0
        items = list(
            db.scalars(
                select(Notification)
                .where(*filters)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    @staticmethod
    def get_notification(
        db: Session, customer_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        notification = db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.customer_id == customer_id,
            )
        )
        if notification is None:
            raise AppError("NOT_FOUND", "Notification not found", 404)
        return notification

    @staticmethod
    def unread_count(db: Session, customer_id: uuid.UUID) -> int:
        return db.scalar(
            select(func.count()).select_from(Notification).where(
                Notification.customer_id == customer_id,
                Notification.is_read.is_(False),
            )
        ) or 0

    @staticmethod
    def mark_read(
        db: Session, customer_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        notification = NotificationService.get_notification(
            db, customer_id, notification_id
        )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            notification.status = "read"
            db.commit()
            db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_read(db: Session, customer_id: uuid.UUID) -> int:
        result = db.execute(
            update(Notification)
            .where(
                Notification.customer_id == customer_id,
                Notification.is_read.is_(False),
            )
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc),
                status="read",
            )
        )
        db.commit()
        return result.rowcount or 0

    @staticmethod
    def delete_notification(
        db: Session, customer_id: uuid.UUID, notification_id: uuid.UUID
    ) -> None:
        notification = NotificationService.get_notification(
            db, customer_id, notification_id
        )
        db.delete(notification)
        db.commit()

    @staticmethod
    def create_notification(
        db: Session,
        customer_id: uuid.UUID,
        title: str,
        message: str,
        notification_type: str,
        channel: str = "in_app",
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[uuid.UUID] = None,
        status: str = "pending",
    ) -> Notification:
        notification = Notification(
            customer_id=customer_id,
            title=title,
            message=message,
            notification_type=notification_type,
            channel=channel,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            status=status,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification
