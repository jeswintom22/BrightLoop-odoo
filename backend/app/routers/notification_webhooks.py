import logging

from fastapi import APIRouter, Depends, Header, Request

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.database import get_db
from app.services.notification_email_service import NotificationEmailService
from sqlalchemy.orm import Session

logger = logging.getLogger("brightloop.notifications.webhook")
router = APIRouter(prefix="/webhooks", tags=["Notification Webhooks"])


@router.post("/resend")
async def resend_webhook(
    request: Request,
    svix_id: str = Header(alias="svix-id"),
    svix_timestamp: str = Header(alias="svix-timestamp"),
    svix_signature: str = Header(alias="svix-signature"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.RESEND_WEBHOOK_SECRET:
        raise AppError(
            "WEBHOOK_NOT_CONFIGURED", "Email webhook is not configured", 503
        )
    try:
        raw_body = (await request.body()).decode("utf-8")
        accepted = NotificationEmailService.apply_webhook(
            db,
            raw_body=raw_body,
            event_id=svix_id,
            timestamp=svix_timestamp,
            signature=svix_signature,
            webhook_secret=settings.RESEND_WEBHOOK_SECRET,
        )
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning("Rejected invalid Resend webhook (event_id=%s)", svix_id)
        raise AppError("INVALID_WEBHOOK", "Webhook signature or payload is invalid", 400) from exc
    return {"accepted": accepted}
