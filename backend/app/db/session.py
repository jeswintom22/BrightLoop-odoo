import time
import logging
from typing import Generator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings

logger = logging.getLogger(__name__)

# Determine if the connection target is SQLite or PostgreSQL
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine_kwargs: Dict[str, Any] = {
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
    "echo": False,
}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Optimizations tailored for Supabase PostgreSQL and Render Free Web Service
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health(db: Session) -> Dict[str, Any]:
    """
    Safely ping the database to verify connectivity.
    Never exposes credentials or internal network addresses.
    """
    start_time = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "dialect": engine.dialect.name
        }
    except SQLAlchemyError as exc:
        logger.error("Database health check failed: %s", str(exc))
        return {
            "status": "unhealthy",
            "error": "Unable to connect to database"
        }
    except Exception as exc:
        logger.error("Unexpected error during database check: %s", str(exc))
        return {
            "status": "unhealthy",
            "error": "Unexpected connection error"
        }
