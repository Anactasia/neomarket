# app/schemas/invoice.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class InvoiceItemCreate(BaseModel):
    """Позиция накладной при создании"""
    sku_id: UUID = Field(..., description="ID SKU")
    quantity: int = Field(..., gt=0, description="Заявленное количество (> 0)")

class InvoiceItemResponse(BaseModel):
    """Позиция накладной в ответе"""
    id: UUID
    sku_id: UUID
    quantity: int
    accepted_quantity: Optional[int] = None
    
    class Config:
        from_attributes = True

class InvoiceCreate(BaseModel):
    """Создание накладной"""
    items: List[InvoiceItemCreate] = Field(..., min_length=1, description="Минимум одна позиция")

class InvoiceResponse(BaseModel):
    """Ответ с накладной"""
    id: UUID
    seller_id: UUID
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    items: List[InvoiceItemResponse] = []
    
    class Config:
        from_attributes = True

class InvoiceAcceptItem(BaseModel):
    """Позиция при приёмке"""
    invoice_item_id: UUID
    accepted_quantity: int = Field(..., ge=0, description="Принятое количество (>= 0)")

class InvoiceAcceptRequest(BaseModel):
    """Запрос на приёмку накладной"""
    accepted_items: Optional[List[InvoiceAcceptItem]] = Field(None, description="Результат приёмки для каждой позиции")

class InvoicePaginatedResponse(BaseModel):
    """Пагинированный ответ со списком накладных"""
    items: List[InvoiceResponse]
    total_count: int
    limit: int
    offset: int