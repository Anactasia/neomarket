# app/schemas/product.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.schemas.common import CategoryRef, Image, CharacteristicValue, SKUInProduct
from app.schemas.validators import validate_slug, validate_title  # ← импорт валидаторов


class ProductStatus(str, Enum):
    """Статусы товара по спецификации"""
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"


class ProductBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    slug: str = Field(..., max_length=500)
    category_id: int = Field(..., gt=0)
    meta_title: Optional[str] = Field(None, max_length=500)
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


# ----- FOR CREATE -----
class ProductCreate(ProductBase):
    seller_id: UUID
    characteristics: List[CharacteristicValue] = []
    
    # ← ПОДКЛЮЧАЕМ ВАЛИДАТОРЫ
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
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    category_id: Optional[int] = Field(None, gt=0)
    characteristics: Optional[List[CharacteristicValue]] = None
    meta_title: Optional[str] = Field(None, max_length=500)
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    
    # ← ПОДКЛЮЧАЕМ ВАЛИДАТОРЫ (с проверкой что поле передано)
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_title(v)
        return v
    


# ----- FOR RESPONSE -----
class ProductResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: ProductStatus
    category: CategoryRef
    images: List[Image] = []
    characteristics: List[CharacteristicValue] = []
    skus: List[SKUInProduct] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


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