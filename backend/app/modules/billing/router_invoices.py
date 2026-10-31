import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ...core.config import Settings, get_settings
from ...core.errors import AppError
from ...core.pagination import Page
from ...core.time import utc_now
from ...deps import (
    CurrentUser,
    get_billing_service,
    get_customer_provider,
    get_db,
    require_roles,
)
from ...services.notification_event_service import notify_invoice_generated
from . import repository as repo
from .emails import send_invoice_email
from .integrations import CustomerProvider
from .models import Invoice
from .pdf import render_invoice_pdf
from .schemas import (
    EmailRequest,
    EmailResult,
    InvoiceCreateRequest,
    InvoiceDetail,
    InvoicePatchRequest,
    InvoiceSummary,
)
from .service_billing import BillingService

router = APIRouter(tags=["invoices"])

READ = Depends(require_roles("admin", "staff"))
WRITE = Depends(require_roles("admin", "staff"))


def _to_summary(invoice: Invoice, names: dict) -> InvoiceSummary:
    out = InvoiceSummary.model_validate(invoice)
    customer = names.get(invoice.customer_id)
    out.customer_name = customer.name if customer else None
    return out


def _to_detail(invoice: Invoice, customers: CustomerProvider) -> InvoiceDetail:
    out = InvoiceDetail.model_validate(invoice)
    customer = customers.get(invoice.customer_id)
    out.customer_name = customer.name if customer else None
    return out


def _must_get(session: Session, invoice_id: uuid.UUID) -> Invoice:
    invoice = repo.get_invoice(session, invoice_id)
    if invoice is None:
        raise AppError("INVOICE_NOT_FOUND", "Invoice not found", 404)
    return invoice


@router.get("/invoices", response_model=Page[InvoiceSummary])
def list_invoices(
    status_: str | None = Query(None, alias="status"),
    customer_id: uuid.UUID | None = None,
    subscription_id: uuid.UUID | None = None,
    overdue: bool = False,
    q: str | None = None,
    issue_from: dt.date | None = None,
    issue_to: dt.date | None = None,
    due_to: dt.date | None = None,
    sort: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db),
    customers: CustomerProvider = Depends(get_customer_provider),
    _user: CurrentUser = READ,
):
    items, total = repo.list_invoices(
        session,
        status=status_,
        customer_id=customer_id,
        subscription_id=subscription_id,
        overdue=overdue,
        q=q,
        issue_from=issue_from,
        issue_to=issue_to,
        due_to=due_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    names = customers.get_many([i.customer_id for i in items])
    return Page(
        items=[_to_summary(i, names) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/invoices",
    response_model=InvoiceDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice(
    body: InvoiceCreateRequest,
    session: Session = Depends(get_db),
    service: BillingService = Depends(get_billing_service),
    customers: CustomerProvider = Depends(get_customer_provider),
    settings: Settings = Depends(get_settings),
    user: CurrentUser = WRITE,
):
    invoice, created = service.generate_invoice(
        session,
        subscription_id=body.subscription_id,
        period_start=body.period_start,
        period_end=body.period_end,
        due_date=body.due_date,
        actor_id=user.id,
    )
    if not created:
        raise AppError(
            "INVOICE_ALREADY_EXISTS",
            "An invoice already exists for this subscription and period",
            409,
            {"existing_invoice_id": str(invoice.id)},
        )
    session.commit()
    notify_invoice_generated(
        session, invoice=invoice, customers=customers, settings=settings
    )
    return _to_detail(invoice, customers)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(
    invoice_id: uuid.UUID,
    session: Session = Depends(get_db),
    customers: CustomerProvider = Depends(get_customer_provider),
    _user: CurrentUser = READ,
):
    return _to_detail(_must_get(session, invoice_id), customers)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceDetail)
def patch_invoice(
    invoice_id: uuid.UUID,
    body: InvoicePatchRequest,
    session: Session = Depends(get_db),
    service: BillingService = Depends(get_billing_service),
    customers: CustomerProvider = Depends(get_customer_provider),
    settings: Settings = Depends(get_settings),
    _user: CurrentUser = WRITE,
):
    invoice = _must_get(session, invoice_id)
    service.patch_draft(
        session, invoice, due_date=body.due_date, notes=body.notes
    )
    session.commit()
    notify_invoice_generated(
        session,
        invoice=invoice,
        customers=customers,
        settings=settings,
        event="updated",
    )
    return _to_detail(invoice, customers)


@router.post("/invoices/{invoice_id}/confirm", response_model=InvoiceDetail)
def confirm_invoice(
    invoice_id: uuid.UUID,
    session: Session = Depends(get_db),
    service: BillingService = Depends(get_billing_service),
    customers: CustomerProvider = Depends(get_customer_provider),
    settings: Settings = Depends(get_settings),
    _user: CurrentUser = WRITE,
):
    invoice = _must_get(session, invoice_id)
    service.confirm_invoice(session, invoice)
    session.commit()
    notify_invoice_generated(
        session,
        invoice=invoice,
        customers=customers,
        settings=settings,
        event="updated",
    )
    return _to_detail(invoice, customers)


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceDetail)
def cancel_invoice(
    invoice_id: uuid.UUID,
    session: Session = Depends(get_db),
    service: BillingService = Depends(get_billing_service),
    customers: CustomerProvider = Depends(get_customer_provider),
    _user: CurrentUser = WRITE,
):
    invoice = _must_get(session, invoice_id)
    service.cancel_invoice(session, invoice)
    session.commit()
    from ...services.notification_delivery_service import NotificationDeliveryService

    NotificationDeliveryService.cancel_invoice_reminders(session, invoice.id)
    return _to_detail(invoice, customers)


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: uuid.UUID,
    session: Session = Depends(get_db),
    customers: CustomerProvider = Depends(get_customer_provider),
    _user: CurrentUser = READ,
):
    invoice = _must_get(session, invoice_id)
    pdf = render_invoice_pdf(invoice, customers.get(invoice.customer_id))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'
        },
    )


@router.post("/invoices/{invoice_id}/email", response_model=EmailResult)
def email_invoice(
    invoice_id: uuid.UUID,
    body: EmailRequest,
    session: Session = Depends(get_db),
    customers: CustomerProvider = Depends(get_customer_provider),
    settings: Settings = Depends(get_settings),
    _user: CurrentUser = WRITE,
):
    invoice = _must_get(session, invoice_id)
    customer = customers.get(invoice.customer_id)
    recipient = body.to or (customer.email if customer else None)
    if not recipient:
        raise AppError("NO_RECIPIENT", "No recipient email available", 400)

    pdf = render_invoice_pdf(invoice, customer)
    sent = send_invoice_email(
        settings=settings,
        invoice=invoice,
        to=recipient,
        pdf_bytes=pdf,
        subject=body.subject,
        message=body.message,
    )
    if not sent:
        return EmailResult(sent=False, reason="email_not_configured")
    invoice.last_emailed_at = utc_now()
    session.commit()
    return EmailResult(sent=True, emailed_at=invoice.last_emailed_at)
