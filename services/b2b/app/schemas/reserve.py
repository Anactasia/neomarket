# app/schemas/reserve.py

"""
Схемы для резервирования товаров (B2C → B2B)
"""
from pydantic import BaseModel, Field
from typing import List
from uuid import UUID


class ReserveItem(BaseModel):
    sku_id: UUID
    quantity: int = Field(...)


class ReserveRequest(BaseModel):
    """Запрос на резервирование от B2C"""
    items: List[ReserveItem]
    order_id: UUID
    ttl_seconds: int = Field(default=900, ge=60, le=3600)


class ReserveResult(BaseModel):
    """Результат по одному SKU"""
    sku_id: UUID
    requested: int
    reserved: int
    available: int


class ReserveResponse(BaseModel):
    """Ответ на резервирование"""
    reservation_id: UUID
    items: List[ReserveResult]