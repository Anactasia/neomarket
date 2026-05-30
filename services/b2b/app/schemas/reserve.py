"""
Схемы для резервирования товаров (B2C → B2B)
Соответствует neomarket-b2b.yaml
"""
from pydantic import BaseModel, Field
from typing import List, Literal
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
    items: List[ReserveItem] = Field(..., min_length=1)


class ReserveSuccessResponse(BaseModel):
    """Ответ на успешное резервирование (200)"""
    order_id: UUID
    status: Literal["RESERVED"] = "RESERVED"
    reserved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReserveErrorResponse(BaseModel):
    """Ответ при неудачном резервировании (409)"""
    code: str = "INSUFFICIENT_STOCK"
    message: str = "Some items are out of stock or have insufficient quantity"
    details: dict = Field(default_factory=dict)


# ─── Unreserve (POST /api/v1/inventory/unreserve) ───

class UnreserveItem(BaseModel):
    sku_id: UUID
    quantity: int = Field(..., gt=0)


class UnreserveRequest(BaseModel):
    """Запрос на снятие резерва (при отмене заказа)"""
    order_id: UUID
    items: List[UnreserveItem] = Field(..., min_length=1)


class UnreserveSuccessResponse(BaseModel):
    """Ответ на успешное снятие резерва (200)"""
    order_id: UUID
    status: Literal["UNRESERVED"] = "UNRESERVED"
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Fulfill (POST /api/v1/inventory/fulfill) ───

class InventoryOrderRequest(BaseModel):
    """Запрос на снятие резерва или списание (fulfill)"""
    order_id: UUID
    items: List[UnreserveItem] = Field(..., min_length=1)


class InventoryOrderResponse(BaseModel):
    """Ответ на успешное снятие резерва или списание (200)"""
    order_id: UUID
    status: Literal["UNRESERVED", "FULFILLED"]
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        from_attributes = True