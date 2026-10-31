from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Quotation,
    QuotationLine,
    Subscription,
    SubscriptionLine,
    LifecycleStatus,
    BillingFrequency,
)
from schemas import (
    QuotationCreate,
    QuotationRead,
    QuotationStatusUpdate,
    SubscriptionConvertRequest,
    SubscriptionLifecycleUpdate,
    SubscriptionRead,
    LifecycleAction,
)

router = APIRouter(tags=["Quotations & Subscriptions"])


# ==========================================
# Helper Utilities
# ==========================================

def calculate_next_billing_date(start_date: date, frequency: str) -> date:
    """Calculates the next billing date based on start date and recurrence frequency."""
    freq = frequency.lower()
    if freq == "daily":
        return start_date + timedelta(days=1)
    elif freq == "weekly":
        return start_date + timedelta(weeks=1)
    elif freq == "yearly":
        try:
            return start_date.replace(year=start_date.year + 1)
        except ValueError:
            # Handles Feb 29 on leap years
            return start_date + timedelta(days=365)
    else:  # default monthly
        # Advance by roughly one calendar month
        new_year = start_date.year + (start_date.month // 12)
        new_month = (start_date.month % 12) + 1
        try:
            return start_date.replace(year=new_year, month=new_month)
        except ValueError:
            # If target month has fewer days (e.g. Jan 31 -> Feb 28)
            return (start_date.replace(year=new_year, month=new_month, day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)


def generate_quotation_number(db: Session, target_date: date) -> str:
    """Generates a sequential quotation reference number like QUO-2026-0001."""
    year = target_date.year
    prefix = f"QUO-{year}-"
    items = (
        db.query(Quotation.quotation_number)
        .filter(Quotation.quotation_number.like(f"{prefix}%"))
        .all()
    )
    max_seq = 0
    for (num,) in items:
        try:
            seq = int(num.split("-")[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue
    return f"{prefix}{max_seq + 1:04d}"


def generate_subscription_number(db: Session, target_date: date) -> str:
    """Generates a sequential subscription reference number like SUB-2026-0001."""
    year = target_date.year
    prefix = f"SUB-{year}-"
    items = (
        db.query(Subscription.subscription_number)
        .filter(Subscription.subscription_number.like(f"{prefix}%"))
        .all()
    )
    max_seq = 0
    for (num,) in items:
        try:
            seq = int(num.split("-")[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue
    return f"{prefix}{max_seq + 1:04d}"


# ==========================================
# Quotations Endpoints
# ==========================================

@router.post(
    "/quotations",
    response_model=QuotationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a quotation with product lines and validity dates",
)
def create_quotation(
    payload: QuotationCreate,
    db: Session = Depends(get_db),
):
    """
    Creates a new sales quotation with validity period and calculated product lines.
    """
    today = date.today()
    quo_number = payload.quotation_number or generate_quotation_number(db, today)

    # Check for duplicate quotation number
    existing = db.query(Quotation).filter(Quotation.quotation_number == quo_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quotation with number '{quo_number}' already exists.",
        )

    # Calculate lines & total
    total_amount = 0.0
    quotation_lines: List[QuotationLine] = []

    for line_in in payload.lines:
        discount = line_in.discount_percent
        tax = line_in.tax_percent
        base_price = line_in.quantity * line_in.unit_price
        subtotal = round(base_price * (1 - (discount / 100.0)), 2)
        total_amount += subtotal

        quotation_lines.append(
            QuotationLine(
                product_id=line_in.product_id,
                product_name=line_in.product_name,
                description=line_in.description,
                quantity=line_in.quantity,
                unit_price=line_in.unit_price,
                discount_percent=discount,
                tax_percent=tax,
                subtotal=subtotal,
                billing_frequency=line_in.billing_frequency,
            )
        )

    quotation = Quotation(
        quotation_number=quo_number,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        customer_email=str(payload.customer_email),
        valid_until=payload.valid_until,
        status=payload.status or LifecycleStatus.DRAFT,
        total_amount=round(total_amount, 2),
        currency=payload.currency.upper(),
        template_name=payload.template_name,
        notes=payload.notes,
        lines=quotation_lines,
    )

    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    return quotation


@router.get(
    "/quotations",
    response_model=List[QuotationRead],
    summary="List all quotations",
)
def list_quotations(
    customer_id: Optional[str] = None,
    status: Optional[LifecycleStatus] = None,
    db: Session = Depends(get_db),
):
    """List quotations with optional filtering by customer and lifecycle status."""
    query = db.query(Quotation)
    if customer_id:
        query = query.filter(Quotation.customer_id == customer_id)
    if status:
        query = query.filter(Quotation.status == status)
    return query.order_by(Quotation.id.desc()).all()


@router.get(
    "/quotations/{quotation_id}",
    response_model=QuotationRead,
    summary="Get quotation details",
)
def get_quotation(quotation_id: int, db: Session = Depends(get_db)):
    """Fetch details of a specific quotation by ID."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quotation with ID {quotation_id} not found.",
        )
    return quotation


@router.post(
    "/quotations/{quotation_id}/confirm",
    response_model=QuotationRead,
    summary="Confirm a quotation",
)
def confirm_quotation(quotation_id: int, db: Session = Depends(get_db)):
    """Convenience endpoint to confirm an accepted quotation so it can be converted to a subscription."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quotation with ID {quotation_id} not found.",
        )

    if quotation.status == LifecycleStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm a closed quotation.",
        )

    quotation.status = LifecycleStatus.CONFIRMED
    db.commit()
    db.refresh(quotation)
    return quotation


# ==========================================
# Subscription Conversion Endpoints
# ==========================================

def _convert_quotation_to_subscription(
    quotation_id: int,
    payload: Optional[SubscriptionConvertRequest],
    db: Session,
) -> Subscription:
    """Core logic to convert a confirmed quotation into an active subscription."""
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quotation with ID {quotation_id} not found.",
        )

    # Check if already converted
    existing_sub = (
        quotation.subscription
        or db.query(Subscription).filter(Subscription.quotation_id == quotation_id).first()
    )
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Quotation {quotation.quotation_number} has already been converted to "
                f"subscription '{existing_sub.subscription_number}'."
            ),
        )

    # Auto-confirm or check Confirmed status
    if payload and payload.auto_confirm:
        quotation.status = LifecycleStatus.CONFIRMED
    elif quotation.status != LifecycleStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Quotation must be in 'Confirmed' status to be converted into an Active subscription. "
                f"Current status is '{quotation.status.value}'."
            ),
        )

    # Check expiration date
    today = date.today()
    if quotation.valid_until < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot convert expired quotation. Valid until was {quotation.valid_until}.",
        )

    # Resolve start date & frequency
    start_date = payload.start_date if payload and payload.start_date else today
    primary_freq = (
        payload.billing_frequency
        if payload and payload.billing_frequency
        else (quotation.lines[0].billing_frequency if quotation.lines else "monthly")
    )

    sub_number = generate_subscription_number(db, start_date)
    next_billing = calculate_next_billing_date(start_date, primary_freq)

    # Copy lines into subscription lines
    sub_lines: List[SubscriptionLine] = []
    for q_line in quotation.lines:
        sub_lines.append(
            SubscriptionLine(
                product_id=q_line.product_id,
                product_name=q_line.product_name,
                description=q_line.description,
                quantity=q_line.quantity,
                unit_price=q_line.unit_price,
                discount_percent=q_line.discount_percent,
                tax_percent=q_line.tax_percent,
                subtotal=q_line.subtotal,
                billing_frequency=q_line.billing_frequency or primary_freq,
            )
        )

    subscription = Subscription(
        subscription_number=sub_number,
        quotation_id=quotation.id,
        customer_id=quotation.customer_id,
        customer_name=quotation.customer_name,
        customer_email=quotation.customer_email,
        status=LifecycleStatus.ACTIVE,
        start_date=start_date,
        next_billing_date=next_billing,
        billing_frequency=primary_freq,
        total_amount=quotation.total_amount,
        currency=quotation.currency,
        notes=payload.notes if payload and payload.notes else quotation.notes,
        lines=sub_lines,
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


@router.post(
    "/subscriptions/convert/{quotation_id}",
    response_model=SubscriptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Convert Confirmed quotation into an Active subscription",
)
def convert_quotation(
    quotation_id: int,
    payload: Optional[SubscriptionConvertRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Converts a Confirmed quotation into an Active subscription,
    auto-generating a unique subscription number like SUB-2026-0001.
    """
    return _convert_quotation_to_subscription(quotation_id, payload, db)


@router.post(
    "/quotations/{quotation_id}/convert",
    response_model=SubscriptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Alias: Convert Confirmed quotation into an Active subscription",
    include_in_schema=True,
)
def convert_quotation_alias(
    quotation_id: int,
    payload: Optional[SubscriptionConvertRequest] = None,
    db: Session = Depends(get_db),
):
    """Alternate route for converting quotation into an active subscription."""
    return _convert_quotation_to_subscription(quotation_id, payload, db)


# ==========================================
# Subscription Lifecycle State Updates
# ==========================================

@router.patch(
    "/subscriptions/{subscription_id}/state",
    response_model=SubscriptionRead,
    summary="Update subscription lifecycle state (pause, resume, close)",
)
def update_subscription_state(
    subscription_id: int,
    payload: SubscriptionLifecycleUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates a subscription's lifecycle state:
    - pause: from Active -> Paused
    - resume: from Paused -> Active
    - close: from Active or Paused -> Closed
    """
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription with ID {subscription_id} not found.",
        )

    now = datetime.now(timezone.utc)
    action = payload.action

    if action == LifecycleAction.PAUSE:
        if subscription.status != LifecycleStatus.ACTIVE:
            if subscription.status == LifecycleStatus.PAUSED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Subscription '{subscription.subscription_number}' is already Paused.",
                )
            if subscription.status == LifecycleStatus.CLOSED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot pause a Closed subscription.",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pause a subscription in '{subscription.status.value}' state. Must be Active.",
            )
        subscription.status = LifecycleStatus.PAUSED
        subscription.paused_at = now
        subscription.pause_reason = payload.reason or "Subscription paused by user request."

    elif action == LifecycleAction.RESUME:
        if subscription.status != LifecycleStatus.PAUSED:
            if subscription.status == LifecycleStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Subscription '{subscription.subscription_number}' is already Active.",
                )
            if subscription.status == LifecycleStatus.CLOSED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot resume a Closed subscription.",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume a subscription in '{subscription.status.value}' state. Must be Paused.",
            )
        subscription.status = LifecycleStatus.ACTIVE
        subscription.paused_at = None
        # Refresh next billing date if needed
        if not subscription.next_billing_date or subscription.next_billing_date < date.today():
            subscription.next_billing_date = calculate_next_billing_date(date.today(), subscription.billing_frequency)

    elif action == LifecycleAction.CLOSE:
        if subscription.status == LifecycleStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription '{subscription.subscription_number}' is already Closed.",
            )
        subscription.status = LifecycleStatus.CLOSED
        subscription.closed_at = now
        subscription.close_reason = payload.reason or "Subscription terminated."

    db.commit()
    db.refresh(subscription)
    return subscription


@router.post(
    "/subscriptions/{subscription_id}/pause",
    response_model=SubscriptionRead,
    summary="Direct action: Pause an active subscription",
)
def pause_subscription(
    subscription_id: int,
    reason: Optional[str] = Query(None, description="Reason for pausing subscription"),
    db: Session = Depends(get_db),
):
    """Direct convenience endpoint to pause an active subscription."""
    return update_subscription_state(
        subscription_id=subscription_id,
        payload=SubscriptionLifecycleUpdate(action=LifecycleAction.PAUSE, reason=reason),
        db=db,
    )


@router.post(
    "/subscriptions/{subscription_id}/resume",
    response_model=SubscriptionRead,
    summary="Direct action: Resume a paused subscription",
)
def resume_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
):
    """Direct convenience endpoint to resume a paused subscription."""
    return update_subscription_state(
        subscription_id=subscription_id,
        payload=SubscriptionLifecycleUpdate(action=LifecycleAction.RESUME),
        db=db,
    )


@router.post(
    "/subscriptions/{subscription_id}/close",
    response_model=SubscriptionRead,
    summary="Direct action: Close a subscription",
)
def close_subscription(
    subscription_id: int,
    reason: Optional[str] = Query(None, description="Reason for closing subscription"),
    db: Session = Depends(get_db),
):
    """Direct convenience endpoint to close a subscription."""
    return update_subscription_state(
        subscription_id=subscription_id,
        payload=SubscriptionLifecycleUpdate(action=LifecycleAction.CLOSE, reason=reason),
        db=db,
    )


@router.get(
    "/subscriptions",
    response_model=List[SubscriptionRead],
    summary="List all subscriptions",
)
def list_subscriptions(
    customer_id: Optional[str] = None,
    status: Optional[LifecycleStatus] = None,
    db: Session = Depends(get_db),
):
    """List subscriptions with optional filtering by customer and lifecycle status."""
    query = db.query(Subscription)
    if customer_id:
        query = query.filter(Subscription.customer_id == customer_id)
    if status:
        query = query.filter(Subscription.status == status)
    return query.order_by(Subscription.id.desc()).all()


@router.get(
    "/subscriptions/{subscription_id}",
    response_model=SubscriptionRead,
    summary="Get subscription details",
)
def get_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """Fetch details of a specific subscription by ID."""
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription with ID {subscription_id} not found.",
        )
    return subscription
