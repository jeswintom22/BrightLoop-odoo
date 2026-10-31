from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.errors import (
    AppError,
    app_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from .modules.billing import (
    router_billing,
    router_dashboard,
    router_internal,
    router_invoices,
    router_payments,
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.project_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(router_invoices.router, prefix="/api/v1")
    app.include_router(router_payments.router, prefix="/api/v1")
    app.include_router(router_billing.router, prefix="/api/v1")
    app.include_router(router_dashboard.router, prefix="/api/v1")
    app.include_router(router_internal.router, prefix="/api/v1")

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
