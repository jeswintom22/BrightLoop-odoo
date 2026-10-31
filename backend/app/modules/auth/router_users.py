"""P1 admin endpoints — /api/v1/users/*, /api/v1/customers/* (staff management,
customer management). Writes are admin-only; customer reads allow staff."""

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.pagination import Page
from ...deps import CurrentUser, get_db, require_roles
from .models import Customer, User
from .schemas import CustomerOut, CustomerUpdate, StaffCreateRequest, UserOut
from . import service

router = APIRouter(tags=["users"])

ADMIN = Depends(require_roles("admin"))
STAFF_OR_ADMIN = Depends(require_roles("admin", "staff"))


@router.get("/users", response_model=Page[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
    session: Session = Depends(get_db),
    _: CurrentUser = ADMIN,
):
    q = sa.select(User).order_by(User.created_at.desc())
    count_q = sa.select(sa.func.count()).select_from(User)
    if role:
        q = q.where(User.role == role)
        count_q = count_q.where(User.role == role)
    total = session.scalar(count_q) or 0
    users = session.scalars(
        q.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page(
        items=[_out(session, u) for u in users],
        total=total, page=page, page_size=page_size,
    )


@router.post("/users/staff", response_model=UserOut, status_code=201)
def create_staff(
    body: StaffCreateRequest,
    session: Session = Depends(get_db),
    _: CurrentUser = ADMIN,
):
    user = service.create_staff(
        session,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role=body.role,
    )
    session.commit()
    return _out(session, user)


@router.get("/customers", response_model=Page[CustomerOut])
def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    session: Session = Depends(get_db),
    _: CurrentUser = STAFF_OR_ADMIN,
):
    q = sa.select(Customer).order_by(Customer.created_at.desc())
    count_q = sa.select(sa.func.count()).select_from(Customer)
    if search:
        like = f"%{search}%"
        q = q.where(sa.or_(Customer.name.ilike(like), Customer.email.ilike(like)))
        count_q = count_q.where(
            sa.or_(Customer.name.ilike(like), Customer.email.ilike(like))
        )
    total = session.scalar(count_q) or 0
    rows = session.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return Page(
        items=[CustomerOut.model_validate(c) for c in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: uuid.UUID,
    session: Session = Depends(get_db),
    _: CurrentUser = STAFF_OR_ADMIN,
):
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise AppError("NOT_FOUND", "Customer not found", 404)
    return CustomerOut.model_validate(customer)


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    session: Session = Depends(get_db),
    _: CurrentUser = STAFF_OR_ADMIN,
):
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise AppError("NOT_FOUND", "Customer not found", 404)
    for f, v in body.model_dump(exclude_unset=True).items():
        setattr(customer, f, v)
    session.commit()
    return CustomerOut.model_validate(customer)


def _out(session: Session, user: User) -> UserOut:
    customer = service.get_customer_for_user(session, user.id)
    return UserOut(
        id=user.id, email=user.email, full_name=user.full_name,
        role=user.role, is_active=user.is_active,
        customer_id=customer.id if customer else None,
    )
