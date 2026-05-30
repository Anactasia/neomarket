# app/schemas/common.py
from pydantic import BaseModel, Field
from typing import Optional, List, Union, TypeVar, Generic
from datetime import datetime
from enum import Enum
from uuid import UUID


class CategoryRef(BaseModel):
    """Ссылка на категорию (по спецификации B2B)"""
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    level: int
    path: List[str]


class Characteristic(BaseModel):
    """Характеристика для запроса (по спецификации B2B)"""
    name: str = Field(..., max_length=255)
    value: str = Field(..., description="Значение характеристики")


class CharacteristicResponse(Characteristic):
    """Характеристика в ответе (с id, по спецификации B2B)"""
    id: UUID


class Error(BaseModel):
    """Стандартный ответ с ошибкой (по канону)"""
    code: str
    message: str
    details: Optional[dict] = None


class ProductImageCreate(BaseModel):
    """Схема для создания изображения товара"""
    url: str = Field(..., description="Ссылка на изображение в S3")
    ordering: int = Field(0, ge=0, description="Порядок отображения")


class ProductImageResponse(BaseModel):
    """Ответ с изображением товара"""
    id: UUID
    url: str
    ordering: int


class ImageEntityType(str, Enum):
    PRODUCT = "PRODUCT"
    SKU = "SKU"


class ImageUploadResponse(BaseModel):
    id: UUID
    url: str
    ordering: int
    entity_type: ImageEntityType
    entity_id: Optional[UUID] = None


# ========== УНИВЕРСАЛЬНАЯ ПАГИНАЦИЯ ==========

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Универсальный пагинированный ответ (по канону)"""
    items: List[T]
    total_count: int
    limit: int
    offset: int