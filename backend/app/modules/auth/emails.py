"""Password-reset email via Resend — no-op without RESEND_API_KEY (same
pattern as billing emails)."""

import logging

from ...core.config import get_settings

logger = logging.getLogger(__name__)


def send_password_reset(to_email: str, reset_url: str) -> bool:
    settings = get_settings()
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY unset — reset email to %s skipped", to_email)
        return False
    try:
        import resend

        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.RESEND_FROM,
                "to": [to_email],
                "subject": "Reset your Brightloop password",
                "html": (
                    "<p>You requested a password reset for your Brightloop "
                    f'account.</p><p><a href="{reset_url}">Reset password</a>'
                    " — this link is valid for 30 minutes and can be used once."
                    "</p><p>If you did not request this, ignore this email.</p>"
                ),
            }
        )
        return True
    except Exception as exc:  # email failure must not break the request
        logger.warning("Password reset email failed: %s", exc)
        return False
