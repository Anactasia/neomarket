# app/schemas/reserve.py

"""
Схемы для резервирования товаров (B2C → B2B)
Соответствует neomarket-b2b.yaml
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


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
    """Ответ на успешное резервирование (200)"""
    reserved: bool = True
    items: List[ReservedItemResponse]


class FailedReserveItem(BaseModel):
    """Проблемный SKU при неудачном резервировании"""
    sku_id: UUID
    requested: int
    available: int
    reason: str  # OUT_OF_STOCK или INSUFFICIENT_STOCK


class ReserveErrorResponse(BaseModel):
    """Ответ при неудачном резервировании (409)"""
    reserved: bool = False
    failed_items: List[FailedReserveItem]


# ─── Unreserve (POST /api/v1/inventory/unreserve) ───

class UnreserveItem(BaseModel):
    sku_id: UUID = Field(..., description="ID SKU")
    quantity: int = Field(..., gt=0, description="Количество для снятия резерва")


class UnreserveRequest(BaseModel):
    """Запрос на снятие резерва (при отмене заказа)"""
    order_id: UUID = Field(..., description="ID заказа в B2C (для идемпотентности)")
    items: List[UnreserveItem] = Field(..., min_length=1, description="Список SKU для снятия резерва")


class UnreserveSuccessResponse(BaseModel):
    """Ответ на успешное снятие резерва (200)"""
    ok: bool = True