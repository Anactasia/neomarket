"""
Общие Pydantic схемы, переиспользуемые между модулями
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import datetime
from uuid import UUID


class CategoryRef(BaseModel):
    """Ссылка на категорию (по спецификации B2B)"""
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    level: int
    path: str


class Image(BaseModel):
    """Изображение товара (для запроса)"""
    url: str
    ordering: int = 0


class CharacteristicValue(BaseModel):
    """Характеристика для запроса (по спецификации B2B)"""
    name: str = Field(..., max_length=255)
    value: Union[str, int, float, bool] = Field(..., description="Значение характеристики")


class CharacteristicValueResponse(BaseModel):
    """Характеристика в ответе (с id, по спецификации B2B)"""
    id: UUID
    name: str = Field(..., max_length=255)
    value: Union[str, int, float, bool] = Field(..., description="Значение характеристики")


class Pagination(BaseModel):
    """Пагинация"""
    limit: int
    offset: int
    total: int


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


class ImageUploadResponse(BaseModel):
    """Ответ на загрузку изображения"""
    id: UUID
    url: str
    ordering: int
    entity_type: str  # PRODUCT или SKU
    entity_id: Optional[UUID] = None
    
    class Config:
        from_attributes = True