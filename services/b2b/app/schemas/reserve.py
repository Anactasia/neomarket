"""
Схемы для резервирования товаров (B2C → B2B)
Соответствует neomarket-b2b.yaml
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone


# ─── Reserve (POST /api/v1/inventory/reserve) ───

class ReserveItem(BaseModel):
    sku_id: UUID = Field(..., description="ID SKU")
    quantity: int = Field(..., gt=0, description="Количество для резервирования")


class ReserveRequest(BaseModel):
    """Запрос на резервирование от B2C"""
    idempotency_key: UUID = Field(..., description="Идемпотентность ключ (TTL 1 час)")
    order_id: UUID = Field(...)
    items: List[ReserveItem] = Field(..., min_length=1, description="Список SKU для резервирования")


class ReservedItemResponse(BaseModel):
    """Результат по одному SKU при успешном резервировании"""
    sku_id: UUID
    reserved_quantity: int
    remaining_stock: int


class ReserveSuccessResponse(BaseModel):
    """Ответ на успешное резервирование (200) - по спецификации"""
    order_id: UUID
    status: str = "RESERVED"
    reserved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FailedReserveItem(BaseModel):
    """Проблемный SKU при неудачном резервировании"""
    sku_id: UUID
    requested: int
    available: int
    reason: str  # OUT_OF_STOCK или INSUFFICIENT_STOCK


class ReserveErrorResponse(BaseModel):
    """Ответ при неудачном резервировании (409) - по спецификации"""
    code: str = "INSUFFICIENT_STOCK"
    message: str = "Some items are out of stock or have insufficient quantity"
    details: dict = Field(default_factory=dict)


# ─── Unreserve (POST /api/v1/inventory/unreserve) ───

class UnreserveItem(BaseModel):
    sku_id: UUID = Field(..., description="ID SKU")
    quantity: int = Field(..., gt=0, description="Количество для снятия резерва")


class UnreserveRequest(BaseModel):
    """Запрос на снятие резерва (при отмене заказа)"""
    order_id: UUID = Field(..., description="ID заказа в B2C (для идемпотентности)")
    items: List[UnreserveItem] = Field(..., min_length=1, description="Список SKU для снятия резерва")


class UnreserveSuccessResponse(BaseModel):
    """Ответ на успешное снятие резерва (200) - по спецификации InventoryOrderResponse"""
    order_id: UUID
    status: str = "UNRESERVED"
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Fulfill (POST /api/v1/inventory/fulfill) ───

class InventoryOrderRequest(BaseModel):
    """Запрос на снятие резерва или списание (fulfill)"""
    order_id: UUID = Field(..., description="ID заказа в B2C (для идемпотентности)")
    items: List[UnreserveItem] = Field(..., min_length=1, description="Список SKU для обработки")


class InventoryOrderResponse(BaseModel):
    """Ответ на успешное снятие резерва или списание (200)"""
    order_id: UUID
    status: str = Field(..., pattern=r"^(UNRESERVED|FULFILLED)$")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        from_attributes = True