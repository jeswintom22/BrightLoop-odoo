from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Single declarative base for ALL modules' models (P1–P4) so Alembic
    sees one metadata tree."""


_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    echo=False,
    **({} if _is_sqlite else {"pool_size": 5, "max_overflow": 10}),
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)


def get_db() -> Generator:
    """Request-scoped DB session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
