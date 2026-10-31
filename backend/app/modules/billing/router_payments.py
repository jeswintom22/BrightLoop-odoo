import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.pagination import Page
from ...deps import (
    CurrentUser,
    get_db,
    require_roles,
)
from . import repository as repo
from .schemas import (
    PaymentCreateRequest,
    PaymentOut,
    PaymentVoidRequest,
)
from .service_payments import PaymentService

router = APIRouter(tags=["payments"])

READ = Depends(require_roles("admin", "finance", "viewer"))
WRITE = Depends(require_roles("admin", "finance"))

_payments = PaymentService()


@router.post("/payments", response_model=PaymentOut)
def record_payment(
    body: PaymentCreateRequest,
    response: Response,
    session: Session = Depends(get_db),
    user: CurrentUser = WRITE,
):
    payment, created = _payments.record_payment(
        session,
        invoice_id=body.invoice_id,
        amount=body.amount,
        method=body.method,
        paid_at=body.paid_at,
        notes=body.notes,
        idempotency_key=body.idempotency_key,
        actor_id=user.id,
    )
    session.commit()
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return payment


@router.get("/payments", response_model=Page[PaymentOut])
def list_payments(
    invoice_id: uuid.UUID | None = None,
    method: str | None = None,
    status_: str | None = Query(None, alias="status"),
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    sort: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    items, total = repo.list_payments(
        session,
        invoice_id=invoice_id,
        method=method,
        status=status_,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: uuid.UUID,
    session: Session = Depends(get_db),
    _user: CurrentUser = READ,
):
    payment = repo.get_payment(session, payment_id)
    if payment is None:
        raise AppError("PAYMENT_NOT_FOUND", "Payment not found", 404)
    return payment


@router.post("/payments/{payment_id}/void", response_model=PaymentOut)
def void_payment(
    payment_id: uuid.UUID,
    body: PaymentVoidRequest,
    session: Session = Depends(get_db),
    user: CurrentUser = WRITE,
):
    payment = _payments.void_payment(
        session, payment_id, reason=body.reason, actor_id=user.id
    )
    session.commit()
    return payment
