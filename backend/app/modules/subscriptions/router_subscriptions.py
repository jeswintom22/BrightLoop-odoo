"""P3 routers — quotation templates, quotations, subscription lifecycle.
All under /api/v1. Writes require admin/staff."""

import uuid
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.pagination import Page
from ...deps import CurrentUser, get_db, require_roles
from .models import Quotation, QuotationTemplate, Subscription
from .schemas import (
    ConvertRequest,
    QuotationCreateRequest,
    QuotationOut,
    SubscriptionOut,
    TemplateCreateRequest,
    TemplateOut,
)
from . import service_subscriptions as svc

router = APIRouter(tags=["subscriptions"])

WRITE = Depends(require_roles("admin", "staff"))
READ = Depends(require_roles("admin", "staff"))


def _paged(session: Session, q, count_q, out, page, page_size):
    total = session.scalar(count_q) or 0
    rows = session.scalars(
        q.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(
        items=[out.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


# --- templates -----------------------------------------------------------------


@router.post("/quotation-templates", response_model=TemplateOut, status_code=201)
def create_template(
    body: TemplateCreateRequest,
    session: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    tpl = svc.create_template(
        session,
        name=body.name,
        description=body.description,
        validity_days=body.validity_days,
        lines=[l.model_dump() for l in body.lines],
    )
    session.commit()
    return tpl


@router.get("/quotation-templates", response_model=Page[TemplateOut])
def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    q = sa.select(QuotationTemplate).order_by(QuotationTemplate.created_at.desc())
    return _paged(
        session, q,
        sa.select(sa.func.count()).select_from(QuotationTemplate),
        TemplateOut, page, page_size,
    )


# --- quotations -----------------------------------------------------------------


@router.post("/quotations", response_model=QuotationOut, status_code=201)
def create_quotation(
    body: QuotationCreateRequest,
    session: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    quotation = svc.create_quotation(
        session,
        customer_id=body.customer_id,
        template_id=body.template_id,
        lines=[l.model_dump() for l in body.lines] if body.lines else None,
        notes=body.notes,
    )
    session.commit()
    return quotation


@router.get("/quotations", response_model=Page[QuotationOut])
def list_quotations(
    customer_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    q = sa.select(Quotation).order_by(Quotation.created_at.desc())
    count_q = sa.select(sa.func.count()).select_from(Quotation)
    if customer_id:
        q = q.where(Quotation.customer_id == customer_id)
        count_q = count_q.where(Quotation.customer_id == customer_id)
    if status:
        q = q.where(Quotation.status == status)
        count_q = count_q.where(Quotation.status == status)
    return _paged(session, q, count_q, QuotationOut, page, page_size)


@router.get("/quotations/{quotation_id}", response_model=QuotationOut)
def get_quotation(
    quotation_id: uuid.UUID,
    session: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    q = session.get(Quotation, quotation_id)
    if q is None:
        raise AppError("NOT_FOUND", "Quotation not found", 404)
    return q


@router.post("/quotations/{quotation_id}/send", response_model=QuotationOut)
def send_quotation(
    quotation_id: uuid.UUID,
    session: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    q = session.get(Quotation, quotation_id)
    if q is None:
        raise AppError("NOT_FOUND", "Quotation not found", 404)
    svc.send_quotation(session, q)
    session.commit()
    return q


@router.post("/quotations/{quotation_id}/confirm", response_model=QuotationOut)
def confirm_quotation(
    quotation_id: uuid.UUID,
    session: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    q = session.get(Quotation, quotation_id)
    if q is None:
        raise AppError("NOT_FOUND", "Quotation not found", 404)
    svc.confirm_quotation(session, q)
    session.commit()
    return q


@router.post(
    "/quotations/{quotation_id}/convert",
    response_model=SubscriptionOut,
    status_code=201,
)
def convert_quotation(
    quotation_id: uuid.UUID,
    body: ConvertRequest,
    session: Session = Depends(get_db),
    _: CurrentUser = WRITE,
):
    q = session.get(Quotation, quotation_id)
    if q is None:
        raise AppError("NOT_FOUND", "Quotation not found", 404)
    sub = svc.convert_to_subscription(
        session, q,
        start_date=body.start_date, payment_terms=body.payment_terms,
    )
    session.commit()
    return sub


# --- subscriptions ---------------------------------------------------------------


@router.get("/subscriptions", response_model=Page[SubscriptionOut])
def list_subscriptions(
    customer_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    q = sa.select(Subscription).order_by(Subscription.created_at.desc())
    count_q = sa.select(sa.func.count()).select_from(Subscription)
    if customer_id:
        q = q.where(Subscription.customer_id == customer_id)
        count_q = count_q.where(Subscription.customer_id == customer_id)
    if status:
        q = q.where(Subscription.status == status)
        count_q = count_q.where(Subscription.status == status)
    return _paged(session, q, count_q, SubscriptionOut, page, page_size)


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(
    subscription_id: uuid.UUID,
    session: Session = Depends(get_db),
    _: CurrentUser = READ,
):
    sub = session.get(Subscription, subscription_id)
    if sub is None:
        raise AppError("NOT_FOUND", "Subscription not found", 404)
    return sub


def _transition(fn):
    def wrapper(
        subscription_id: uuid.UUID,
        session: Session = Depends(get_db),
        _: CurrentUser = WRITE,
    ):
        sub = fn(session, subscription_id)
        session.commit()
        return sub

    return wrapper


router.post("/subscriptions/{subscription_id}/activate", response_model=SubscriptionOut)(
    _transition(svc.activate)
)
router.post("/subscriptions/{subscription_id}/pause", response_model=SubscriptionOut)(
    _transition(svc.pause)
)
router.post("/subscriptions/{subscription_id}/resume", response_model=SubscriptionOut)(
    _transition(svc.resume)
)
router.post("/subscriptions/{subscription_id}/renew", response_model=SubscriptionOut)(
    _transition(svc.renew)
)
router.post("/subscriptions/{subscription_id}/close", response_model=SubscriptionOut)(
    _transition(svc.close)
)
