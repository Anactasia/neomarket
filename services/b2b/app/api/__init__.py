from fastapi import APIRouter

from app.api.products import router as products_router
from app.api.sellers import router as sellers_router
from app.api.categories import router as categories_router
from app.api.skus import router as skus_router
from app.api.invoices import router as invoices_router
from app.api.reserve import router as reserve_router
from app.api.internal import router as internal_router

router = APIRouter(prefix="/api/v1")

router.include_router(products_router, prefix="/products", tags=["Products"])
router.include_router(sellers_router, prefix="/sellers", tags=["Sellers"])
router.include_router(categories_router, prefix="/categories", tags=["Categories"])
router.include_router(skus_router, prefix="/skus", tags=["SKU"])
router.include_router(invoices_router, prefix="/invoices", tags=["Invoices"])


# Дополнительные роутеры
router.include_router(reserve_router, prefix="/reserve", tags=["Reservation"])
router.include_router(internal_router, prefix="/internal", tags=["Internal"])

# Админ-роутеры (если есть)
# router.include_router(admin_categories_router, prefix=\"/admin/categories\", tags=[\"Admin Categories\"])