# app/schemas/product.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.schemas.sku import SKUPublicResponse, SKUInProduct
from app.schemas.common import (
    CategoryRef, 
    CharacteristicValue, 
    ProductImageCreate,
    ProductImageResponse,
    CharacteristicValueResponse
)


class ProductStatus(str, Enum):
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    HARD_BLOCKED = "HARD_BLOCKED"


class FieldReport(BaseModel):
    """Замечание по конкретному полю товара или SKU"""
    field_name: str = Field(..., description="Имя поля")
    sku_id: Optional[UUID] = Field(None, description="ID SKU (null если замечание к товару)")
    comment: str = Field(..., max_length=1000)

    class Config:
        from_attributes = True


class BlockingReason(BaseModel):
    """Причина блокировки товара"""
    id: UUID
    title: str = Field(..., description="Текст причины")
    comment: Optional[str] = Field(None, max_length=2000)

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    """Создание товара (по спецификации B2B)"""
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=5000)
    category_id: UUID
    slug: Optional[str] = None
    images: List[ProductImageCreate] = Field(default_factory=list)
    characteristics: List[CharacteristicValue] = Field(default_factory=list)
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('title is required')
        return v.strip()


class ProductUpdate(BaseModel):
    """Обновление товара (PATCH, все поля опциональны)"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    characteristics: Optional[List[CharacteristicValue]] = None
    # images управляется через отдельные эндпоинты


class ProductResponse(BaseModel):
    """Полный ответ с товаром (seller view)"""
    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    deleted: bool
    blocking_reason_id: Optional[UUID] = None  
    moderator_comment: Optional[str] = None
    images: List[ProductImageResponse]
    characteristics: List[CharacteristicValueResponse]
    skus: List[SKUInProduct] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Product(BaseModel):
    """Базовая модель товара для БД"""
    id: UUID
    seller_id: UUID
    status: str
    title: str
    description: Optional[str] = None
    category_id: UUID
    created_at: datetime
    updated_at: datetime  
    
    class Config:
        from_attributes = True


# ───────────────────── Public Catalog Schemas ─────────────────────

class ProductPublicShortResponse(BaseModel):
    """Краткая карточка товара для витрины"""
    id: UUID
    title: str
    slug: str
    status: ProductStatus
    category_id: UUID
    created_at: datetime
    min_price: int
    cover_image: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProductPublicResponse(BaseModel):
    """Полная публичная карточка товара для витрины (по спецификации B2B)"""
    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    images: List[ProductImageResponse]
    characteristics: List[CharacteristicValueResponse]
    skus: List[SKUPublicResponse]  # ← из sku.py
    created_at: datetime
    updated_at: datetime  
    
    class Config:
        from_attributes = True


class ProductShortResponse(BaseModel):
    """Краткая карточка товара для списка продавца"""
    id: UUID
    title: str
    slug: str
    status: ProductStatus
    category_id: UUID
    deleted: bool
    created_at: datetime
    min_price: int
    cover_image: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProductPaginatedResponse(BaseModel):
    """Пагинированный ответ списка товаров продавца"""
    items: List[ProductShortResponse]
    total_count: int
    limit: int
    offset: int


class ProductPublicPaginatedResponse(BaseModel):
    """Пагинированный ответ публичного каталога"""
    items: List[ProductPublicShortResponse]
    total_count: int
    limit: int
    offset: int


class ImageAttachRequest(BaseModel):
    """Прикрепление изображения к товару/SKU"""
    image_id: Optional[UUID] = None
    url: Optional[str] = None
    ordering: int = 0


class ImageUpdateRequest(BaseModel):
    """Обновление изображения товара/SKU"""
    url: Optional[str] = None
    ordering: Optional[int] = None


class BatchProductIdsRequest(BaseModel):
    """Запрос batch-получения товаров по ID"""
    product_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    
    class Config:
        from_attributes = True