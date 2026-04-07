# app/schemas/invoice.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class InvoiceItemBase(BaseModel):
    sku_id: UUID
    quantity: int = Field(...)
    price: Optional[int] = None

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItem(InvoiceItemBase):
    id: UUID
    invoice_id: UUID
    accepted_quantity: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    invoice_number: str = Field(..., max_length=50)
    warehouse_id: Optional[int] = None

class InvoiceCreate(InvoiceBase):
    seller_id: UUID
    items: List[InvoiceItemCreate]

class Invoice(InvoiceBase):
    id: UUID
    seller_id: UUID
    status: str
    received_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[InvoiceItem] = []

    class Config:
        from_attributes = True