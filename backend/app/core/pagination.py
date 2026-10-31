from typing import Generic, TypeVar

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.orm import Session

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def paginate(session: Session, stmt: sa.Select, page: int, page_size: int) -> tuple[list, int]:
    total = session.scalar(
        sa.select(sa.func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0
    rows = session.execute(
        stmt.limit(page_size).offset((page - 1) * page_size)
    ).scalars().all()
    return rows, total


SORT_WHITELIST = {
    "created_at": "created_at",
    "issue_date": "issue_date",
    "due_date": "due_date",
    "total_amount": "total_amount",
    "paid_at": "paid_at",
}


def apply_sort(stmt: sa.Select, model, sort: str | None, default_col: str) -> sa.Select:
    """`?sort=-created_at` style ordering against a small whitelist."""
    key = (sort or default_col).lstrip("-")
    col_name = SORT_WHITELIST.get(key, default_col)
    col = getattr(model, col_name, None)
    if col is None:
        col = getattr(model, default_col.lstrip("-"))
    return stmt.order_by(col.desc() if (sort or "").startswith("-") else col.asc())
