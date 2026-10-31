"""P1 auth endpoints — /api/v1/auth/*"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...deps import CurrentUser, get_current_user, get_db
from .emails import send_password_reset
from .models import Customer
from .schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from . import service

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(session: Session, user) -> UserOut:
    customer = service.get_customer_for_user(session, user.id)
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        customer_id=customer.id if customer else None,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, session: Session = Depends(get_db)):
    user, token = service.register_customer(
        session,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone=body.phone,
        billing_address=body.billing_address,
    )
    session.commit()
    return TokenResponse(access_token=token, user=_user_out(session, user))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_db)):
    user, token = service.login(
        session, email=body.email, password=body.password
    )
    session.commit()
    return TokenResponse(access_token=token, user=_user_out(session, user))


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, session: Session = Depends(get_db)):
    """Always 200 with the same body — never reveals whether the email exists."""
    raw = service.request_password_reset(session, email=body.email)
    session.commit()
    if raw is not None:
        base = get_settings().FRONTEND_URL.rstrip("/")
        send_password_reset(
            body.email, f"{base}/reset-password?token={raw}"
        )
    return {"ok": True, "message": "If that email is registered, a reset link was sent."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, session: Session = Depends(get_db)):
    service.reset_password(
        session, token=body.token, new_password=body.new_password
    )
    session.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db)):
    import uuid as _uuid
    from .models import User

    db_user = session.get(User, _uuid.UUID(str(user.id))) or session.get(User, user.id)
    if db_user is None:
        # dev-bypass identity has no DB row
        return UserOut(
            id=user.id, email=user.email, full_name=user.email.split("@")[0],
            role=user.roles[0] if user.roles else "customer",
            is_active=True, customer_id=None,
        )
    return _user_out(session, db_user)
