from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import (
    CurrentUser,
    get_current_user,
    get_db,
    get_notification_customer_id,
)
from app.schemas.notification_preference import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)
from app.services.notification_preference_service import (
    NotificationPreferenceService,
)

router = APIRouter(prefix="/notification-preferences", tags=["Notification Preferences"])


@router.get(
    "",
    response_model=NotificationPreferenceResponse,
    summary="Get or initialize the authenticated customer's notification preferences",
)
def get_preferences(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    customer_id = get_notification_customer_id(db, user)
    return NotificationPreferenceService.get_or_create(db, customer_id)


@router.put(
    "",
    response_model=NotificationPreferenceResponse,
    summary="Update the authenticated customer's notification preferences",
)
def update_preferences(
    preferences_in: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    customer_id = get_notification_customer_id(db, user)
    return NotificationPreferenceService.update(db, customer_id, preferences_in)
