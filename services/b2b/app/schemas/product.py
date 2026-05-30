# app/schemas/product.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.schemas.sku import SKUResponse, SKUPublicResponse
from app.schemas.common import (
    Characteristic,
    CharacteristicResponse,
    ProductImageCreate,
    ProductImageResponse,
)
from app.schemas.moderation import FieldReport, BlockingReason


class ProductStatus(str, Enum):
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    HARD_BLOCKED = "HARD_BLOCKED"


class ProductCreate(BaseModel):
    """Создание товара (по спецификации B2B)"""
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=5000)
    category_id: UUID
    slug: Optional[str] = None
    images: List[ProductImageCreate] = Field(default_factory=list)
    characteristics: List[Characteristic] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Обновление товара (PATCH, все поля опциональны) (по спецификации B2B)"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    characteristics: Optional[List[Characteristic]] = None


class ProductResponse(BaseModel):
    """Полный ответ с товаром (seller view) (по спецификации B2B)"""
    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    deleted: bool
    blocking_reason_id: Optional[UUID] = None      # ← добавлено
    moderator_comment: Optional[str] = None        # ← добавлено
    images: List[ProductImageResponse]
    characteristics: List[CharacteristicResponse]
    skus: List[SKUResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductDetailResponse(ProductResponse):
    """Детальный ответ с товаром (включая блокировки) (по спецификации B2B)"""
    blocked: bool
    blocking_reason: Optional[BlockingReason] = None
    field_reports: List[FieldReport] = []

    class Config:
        from_attributes = True


# ───────────────────── Public Catalog Schemas ─────────────────────

class ProductPublicShortResponse(BaseModel):
    """Краткая карточка товара для витрины (по спецификации B2B)"""
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
    characteristics: List[CharacteristicResponse]
    skus: List[SKUPublicResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductShortResponse(BaseModel):
    """Краткая карточка товара для списка продавца (по спецификации B2B)"""
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
    """Пагинированный ответ списка товаров продавца (по спецификации B2B)"""
    items: List[ProductShortResponse]
    total_count: int
    limit: int
    offset: int


class ProductPublicPaginatedResponse(BaseModel):
    """Пагинированный ответ публичного каталога (по спецификации B2B)"""
    items: List[ProductPublicShortResponse]
    total_count: int
    limit: int
    offset: int


class ImageAttachRequest(BaseModel):
    """Прикрепление изображения к товару/SKU (по спецификации B2B)"""
    image_id: Optional[UUID] = None
    url: Optional[str] = None
    ordering: int = 0


class ImageUpdateRequest(BaseModel):
    """Обновление изображения товара/SKU (по спецификации B2B)"""
    url: Optional[str] = None
    ordering: Optional[int] = None


class BatchProductIdsRequest(BaseModel):
    """Запрос batch-получения товаров по ID (по спецификации B2B)"""
    product_ids: List[UUID] = Field(..., min_length=1, max_length=100)