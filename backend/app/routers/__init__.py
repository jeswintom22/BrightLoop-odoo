from app.routers.products import router as products_router
from app.routers.product_variants import router as variants_router
from app.routers.subscription_plans import router as plans_router
from app.routers.taxes import router as taxes_router
from app.routers.notifications import router as notifications_router
from app.routers.notification_preferences import (
    router as notification_preferences_router,
)

__all__ = [
    "products_router",
    "variants_router",
    "plans_router",
    "taxes_router",
    "notifications_router",
    "notification_preferences_router",
]
