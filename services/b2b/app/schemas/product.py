# app/schemas/product.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.schemas.validators import validate_slug, validate_title

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


# ----- FOR CREATE -----
class ProductCreate(ProductBase):
    seller_id: UUID  # временно, потом будет из токена


class ProductCreateWithValidation(ProductCreate):
    """Схема для создания товара с валидацией"""
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        return validate_title(v)
    
    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return validate_slug(v)


# ----- FOR UPDATE -----
class ProductUpdate(BaseModel):
    """Схема для обновления товара (все поля опциональные)"""
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    category_id: Optional[int] = None
    meta_title: Optional[str] = Field(None, max_length=500)
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


class ProductUpdateWithValidation(ProductUpdate):
    """Схема для обновления товара с валидацией"""
    
    @field_validator('title', check_fields=False)
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_title(v)
        return v
    
    @field_validator('slug', check_fields=False)
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_slug(v)
        return v


# ----- FOR RESPONSE -----
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