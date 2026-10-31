from app.routers.products import router as products_router
from app.routers.product_variants import router as variants_router
from app.routers.subscription_plans import router as plans_router
from app.routers.taxes import router as taxes_router

__all__ = ["products_router", "variants_router", "plans_router", "taxes_router"]
