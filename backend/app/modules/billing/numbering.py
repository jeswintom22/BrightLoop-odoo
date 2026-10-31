"""Invoice/payment number allocation via row-locked counters.

INV-2026-000042 / PAY-2026-000123. Numbers are allocated inside the caller's
transaction (SELECT ... FOR UPDATE), so a rollback never burns a number.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.errors import AppError
from .models import NumberCounter

_PREFIX = {"invoice": "INV", "payment": "PAY"}


def allocate_number(session: Session, name: str, year: int, width: int = 6) -> str:
    for _ in range(3):
        row = session.execute(
            select(NumberCounter)
            .where(NumberCounter.name == name, NumberCounter.year == year)
            .with_for_update()
        ).scalar_one_or_none()

        if row is not None:
            value = row.next_value
            row.next_value = value + 1
            session.flush()
            return f"{_PREFIX[name]}-{year}-{value:0{width}d}"

        try:
            with session.begin_nested():
                session.add(NumberCounter(name=name, year=year, next_value=1))
        except IntegrityError:
            continue  # another transaction won the insert race — reselect

    raise AppError("NUMBERING_FAILED", f"Could not allocate {name} number", 500)
