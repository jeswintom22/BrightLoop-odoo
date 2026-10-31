from fastapi import Response
from main import root
from app.api.health import health_check
from app.db.session import SessionLocal, check_db_health


def test_root_endpoint():
    """Test the root endpoint response and metadata."""
    res = root()
    assert "message" in res
    assert res["health"] == "/health"
    assert res["docs"] == "/docs"
    assert res["version"] == "1.0.0"


def test_health_check_endpoint():
    """Test health check route and verify database connectivity."""
    db = SessionLocal()
    try:
        response = Response()
        res = health_check(response=response, db=db)
        assert res["status"] == "healthy"
        assert res["database"]["status"] == "healthy"
        assert "latency_ms" in res["database"]
        # Ensure credentials are not leaked
        assert "password" not in str(res).lower()
    finally:
        db.close()


def test_session_lifecycle():
    """Verify that SQLAlchemy sessions create, query, and close properly."""
    db = SessionLocal()
    try:
        health = check_db_health(db)
        assert health["status"] == "healthy"
        assert health["dialect"] in ["sqlite", "postgresql"]
    finally:
        db.close()
