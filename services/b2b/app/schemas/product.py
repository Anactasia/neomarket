from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.schemas.common import (
    CategoryRef, 
    CharacteristicValue, 
    SKUInProduct,
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
    field_name: str = Field(..., description="Имя поля: title, description, product_images, category, sku_name, sku_image, sku_price")
    sku_id: Optional[UUID] = Field(None, description="ID SKU (null если замечание к товару)")
    comment: str = Field(..., max_length=1000, description="Комментарий модератора")

    class Config:
        from_attributes = True


class BlockingReason(BaseModel):
    """Причина блокировки товара"""
    id: UUID
    title: str = Field(..., description="Текст причины")
    comment: Optional[str] = Field(None, max_length=2000, description="Дополнительный комментарий модератора")

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=5000)
    category_id: UUID
    images: List[ProductImageCreate] = Field(default_factory=list)
    characteristics: List[CharacteristicValue] = Field(default_factory=list)
    slug: Optional[str] = None
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('title is required')
        return v.strip()
    
    # @field_validator('description')
    # @classmethod
    # def validate_description(cls, v: str) -> str:
    #     if not v or not v.strip():
    #         raise ValueError('description is required')
    #     return v.strip()


class ProductResponse(BaseModel):
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


class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    characteristics: Optional[List[CharacteristicValue]] = None
    images: Optional[List[ProductImageResponse]] = None  # ← Добавлено для поддержки PATCH изображений


class Product(BaseModel):
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


class SKUPublicResponse(BaseModel):
    """Публичный SKU (без cost_price, reserved_quantity)"""
    id: UUID
    product_id: UUID
    name: str
    price: int
    discount: int
    stock_quantity: int
    active_quantity: int
    article: Optional[str] = None
    images: List[ProductImageResponse] = []
    characteristics: List[CharacteristicValueResponse] = []
    
    class Config:
        from_attributes = True


class ProductPublicResponse(BaseModel):
    """Полная публичная карточка товара для витрины"""
    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    images: List[ProductImageResponse]
    characteristics: List[CharacteristicValueResponse]
    skus: List[SKUPublicResponse]
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
    
    class Config:
        from_attributes = True


class ProductPublicPaginatedResponse(BaseModel):
    """Пагинированный ответ публичного каталога"""
    items: List[ProductPublicShortResponse]
    total_count: int
    limit: int
    offset: int
    
    class Config:
        from_attributes = True


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
    product_ids: List[UUID] = Field(..., min_length=1, max_length=100, description="Список product_id (макс 100)")
    
    class Config:
        from_attributes = True