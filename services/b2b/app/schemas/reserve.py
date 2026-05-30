"""
Схемы для резервирования товаров (B2C → B2B)
Соответствует neomarket-b2b.yaml
"""
from pydantic import BaseModel, Field
from typing import List, Literal
from uuid import UUID
from datetime import datetime, timezone


# ─── InventoryItem (общая схема для всех inventory операций) ───

class InventoryItem(BaseModel):
    """Позиция для резервирования/снятия/списания (по спецификации B2B)"""
    sku_id: UUID = Field(..., description="ID SKU")
    quantity: int = Field(..., gt=0, description="Количество")


# ─── Reserve (POST /api/v1/inventory/reserve) ───

class ReserveRequest(BaseModel):
    """Запрос на резервирование от B2C (по спецификации B2B)"""
    idempotency_key: UUID = Field(..., description="Идемпотентность ключ (TTL 1 час)")
    order_id: UUID = Field(...)
    items: List[InventoryItem] = Field(..., min_length=1)


class ReserveResponse(BaseModel):
    """Ответ на успешное резервирование (по спецификации B2B)"""
    order_id: UUID
    status: Literal["RESERVED"] = "RESERVED"
    reserved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Unreserve (POST /api/v1/inventory/unreserve) ───
# ─── Fulfill (POST /api/v1/inventory/fulfill) ───

class InventoryOrderRequest(BaseModel):
    """Запрос на снятие резерва или списание (по спецификации B2B)"""
    order_id: UUID
    items: List[InventoryItem] = Field(..., min_length=1)


class InventoryOrderResponse(BaseModel):
    """Ответ на успешное снятие резерва или списание (по спецификации B2B)"""
    order_id: UUID
    status: Literal["UNRESERVED", "FULFILLED"]
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        from_attributes = True