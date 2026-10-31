import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.deps import CurrentUser, get_current_user, get_db
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    NotificationType,
    UnreadCountResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List the authenticated customer's notifications",
)
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    notification_type: Optional[NotificationType] = None,
    is_read: Optional[bool] = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    items, total = NotificationService.list_notifications(
        db,
        customer_id=user.id,
        page=page,
        page_size=page_size,
        notification_type=notification_type,
        is_read=is_read,
    )
    return NotificationListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get the authenticated customer's unread notification count",
)
def unread_count(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return UnreadCountResponse(
        unread_count=NotificationService.unread_count(db, user.id)
    )


@router.patch("/read-all", summary="Mark all of the customer's notifications as read")
def mark_all_read(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return {
        "updated_count": NotificationService.mark_all_read(db, user.id),
    }


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Get a notification owned by the authenticated customer",
)
def get_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return NotificationService.get_notification(db, user.id, notification_id)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a customer-owned notification as read",
)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return NotificationService.mark_read(db, user.id, notification_id)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a notification owned by the authenticated customer",
)
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    NotificationService.delete_notification(db, user.id, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
