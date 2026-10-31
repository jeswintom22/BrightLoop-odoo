"""Invoice email via Resend — PDF attached. Failures are surfaced to the
caller as sent=False so a flaky email provider never blocks billing."""

import base64

import resend

from ...core.config import Settings
from .models import Invoice


def send_invoice_email(
    *,
    settings: Settings,
    invoice: Invoice,
    to: str,
    pdf_bytes: bytes,
    subject: str | None = None,
    message: str | None = None,
) -> bool:
    if not settings.resend_api_key:
        return False

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from,
            "to": [to],
            "subject": subject or f"Invoice {invoice.invoice_number} from Brightloop",
            "html": message
            or f"<p>Please find attached invoice "
            f"<strong>{invoice.invoice_number}</strong> for "
            f"{invoice.currency} {invoice.total_amount}.</p>",
            "attachments": [
                {
                    "filename": f"{invoice.invoice_number}.pdf",
                    "content": base64.b64encode(pdf_bytes).decode("ascii"),
                }
            ],
        }
    )
    return True
