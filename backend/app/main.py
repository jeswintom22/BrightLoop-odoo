import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .core.config import get_settings
from .core.errors import (
    AppError,
    app_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from .api.health import router as health_router
from .routers.products import router as products_router
from .routers.product_variants import router as variants_router
from .routers.subscription_plans import router as plans_router
from .routers.taxes import router as taxes_router
from .routers.discounts import router as discounts_router
from .modules.billing import (
    router_billing,
    router_dashboard,
    router_internal,
    router_invoices,
    router_payments,
)
from .modules.subscriptions import router as subscriptions_router

logger = logging.getLogger("brightloop.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("Starting up %s in %s mode", settings.PROJECT_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    origins = list(settings.CORS_ORIGINS)
    if settings.FRONTEND_URL not in origins and "*" not in origins:
        origins.append(settings.FRONTEND_URL)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    # Ops/health (no version prefix)
    app.include_router(health_router)

    # Person 2 — catalog (products & variants)
    app.include_router(products_router, prefix=settings.API_V1_STR)
    app.include_router(variants_router, prefix=settings.API_V1_STR)
    app.include_router(plans_router, prefix="/api")
    app.include_router(plans_router, prefix=settings.API_V1_STR)
    app.include_router(taxes_router, prefix="/api")
    app.include_router(taxes_router, prefix=settings.API_V1_STR)
    app.include_router(discounts_router, prefix="/api")
    app.include_router(discounts_router, prefix=settings.API_V1_STR)

    # Person 4 — billing, payments & finance dashboard
    app.include_router(router_invoices.router, prefix="/api/v1")
    app.include_router(router_payments.router, prefix="/api/v1")
    app.include_router(router_billing.router, prefix="/api/v1")
    app.include_router(router_dashboard.router, prefix="/api/v1")
    app.include_router(router_internal.router, prefix="/api/v1")

    # Person 3 — quotations & subscriptions
    app.include_router(subscriptions_router, prefix="/api/v1")
    app.include_router(subscriptions_router)

    app.add_api_route("/", root, methods=["GET"], tags=["Root"], summary="API Root & Overview")

    @app.get("/api/v1/health")
    def api_health() -> dict:
        return {"status": "ok"}

    return app


def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": "/health",
    }


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error occurred: %s", str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "A database error occurred. Please try again later.",
                "details": {},
            }
        },
    )


app = create_app()
