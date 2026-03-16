# app/schemas/product.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class ProductStatus(str):
    DRAFT = "DRAFT"
    PENDING_MODERATION = "PENDING_MODERATION"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"

class ProductBase(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    slug: str = Field(..., max_length=500)
    category_id: int
    meta_title: Optional[str] = Field(None, max_length=500)
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None

class ProductCreate(ProductBase):
    seller_id: UUID

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    category_id: Optional[int] = None
    meta_title: Optional[str] = Field(None, max_length=500)
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None

class Product(ProductBase):
    id: int
    seller_id: UUID
    status: str
    main_image_id: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True