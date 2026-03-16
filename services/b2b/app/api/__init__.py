# app/api/__init__.py
from fastapi import APIRouter

from app.api.products import router as products_router
from app.api.sellers import router as sellers_router
from app.api.categories import router as categories_router
from app.api.skus import router as skus_router
from app.api.invoices import router as invoices_router

# Создаем единый роутер с префиксом /api/v1
router = APIRouter(prefix="/api/v1")

# Подключаем все роутеры
router.include_router(products_router)
router.include_router(sellers_router)
router.include_router(categories_router)
router.include_router(skus_router)
router.include_router(invoices_router)