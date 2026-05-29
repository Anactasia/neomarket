from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import router as api_router
from app.api.auth import router as auth_router  
from app.core.logger import setup_logging
from app.config import settings  # ← добавить импорт


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


# ==================== ВАЛИДАЦИЯ ПРИ СТАРТЕ ====================
@app.on_event("startup")
async def validate_config():
    """
    Проверяет, что все обязательные переменные окружения заданы.
    Если какой-то ключ отсутствует — приложение не стартует.
    """
    try:
        settings.validate_service_keys()
        print("✅ Service keys validated successfully")
        print(f"   - B2C_TO_B2B_KEY: {'✓ set' if settings.B2C_TO_B2B_KEY else '✗ missing'}")
        print(f"   - B2B_TO_MOD_KEY: {'✓ set' if settings.B2B_TO_MOD_KEY else '✗ missing'}")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        raise RuntimeError(f"Missing required environment variables: {e}")


# ==================== ОБРАБОТЧИКИ ОШИБОК ====================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = exc.errors()
    error_messages = []
    
    for error in errors:
        field = ".".join(str(loc) for loc in error["loc"])
        msg = error["msg"]
        
        if "field required" in msg:
            error_messages.append(f"{field} is required")
        else:
            error_messages.append(msg)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  
        content={
            "code": "INVALID_REQUEST",
            "message": error_messages[0] if error_messages else "Validation error"
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """
    Глобальный обработчик HTTPException для возврата flat-формата ошибок.
    Возвращает {"code": "...", "message": "..."} вместо {"detail": {...}}.
    """
    # Проверяем, есть ли уже detail в формате {"code", "message"}
    if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
        # Для 409 CONFLICT оставляем оригинальный формат (reserved, failed_items)
        if exc.status_code == 409 and "reserved" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
            )
        # Если есть code и message - оставляем как есть
        if "code" in exc.detail and "message" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
            )
    # Если detail не в нужном формате, оборачиваем
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": getattr(exc, 'code', f"HTTP_{exc.status_code}"),
            "message": str(exc.detail) if isinstance(exc.detail, str) else "An error occurred"
        }
    )


# ==================== CORS ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== РОУТЕРЫ ====================
app.include_router(auth_router, prefix="/api/v1")      
app.include_router(api_router)       


# ==================== HEALTH CHECKS ====================
@app.get("/")
async def root():
    return {
        "service": "NeoMarket B2B",
        "version": "0.1.0",
        "docs": "/api/docs",
        "auth": "/api/auth"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "b2b",
        "database": "connected"
    }