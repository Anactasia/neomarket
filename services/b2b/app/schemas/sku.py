# app/schemas/sku.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SKUBase(BaseModel):
    product_id: int
    seller_sku: Optional[str] = Field(None, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    name: str = Field(..., max_length=500)
    price: int = Field(..., gt=0)  # в копейках
    compare_at_price: Optional[int] = None
    quantity: int = Field(0, ge=0)
    is_active: bool = True

class SKUCreate(SKUBase):
    pass

class SKUUpdate(BaseModel):
    seller_sku: Optional[str] = Field(None, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=500)
    price: Optional[int] = Field(None, gt=0)
    compare_at_price: Optional[int] = None
    quantity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class SKU(SKUBase):
    id: int
    main_image_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True