# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router  # импортируем единый роутер
from app.core.logger import setup_logging


# Настройка логирования
setup_logging()

# Создание приложения
app = FastAPI(
    title="NeoMarket B2B Service",
    description="Кабинет продавца: управление товарами, SKU, накладными",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # в проде заменить на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем единый роутер (он уже содержит /api/v1 префикс)
app.include_router(api_router)


@app.get("/")
async def root():
    """Корневой endpoint с информацией о сервисе"""
    return {
        "service": "NeoMarket B2B",
        "version": "0.1.0",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "ok",
        "service": "b2b",
        "database": "connected"  # позже можно добавить реальную проверку БД
    }