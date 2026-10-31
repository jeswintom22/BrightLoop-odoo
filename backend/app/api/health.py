from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db, check_db_health

router = APIRouter(tags=["Health"])


@router.get("/health", summary="System Health & Database Connectivity Check")
def health_check(response: Response, db: Session = Depends(get_db)):
    """
    Checks the status of the FastAPI service and probes database connectivity.
    Reports latency and dialect without exposing sensitive connection credentials.
    """
    db_result = check_db_health(db)
    is_db_healthy = db_result.get("status") == "healthy"

    if not is_db_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if is_db_healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "database": db_result
    }
