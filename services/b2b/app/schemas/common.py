"""
Общие Pydantic схемы, переиспользуемые между модулями
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class CategoryRef(BaseModel):
    """Ссылка на категорию (для Product)"""
    id: UUID
    name: str


class Image(BaseModel):
    """Изображение товара (для запроса)"""
    url: str
    ordering: int = 0


class ImageResponse(BaseModel):
    """Ответ с изображением (по общей спецификации)"""
    id: UUID                              # ← ДОБАВИТЬ id
    url: str
    ordering: int = 0


class CharacteristicValue(BaseModel):
    """Характеристика для запроса (свободные name/value)"""
    name: str = Field(..., max_length=255)
    value: str = Field(..., max_length=1000)


class CharacteristicValueResponse(BaseModel):
    """Характеристика в ответе (по общей спецификации — с id)"""
    id: UUID
    name: str = Field(..., max_length=255)
    value: str = Field(..., max_length=1000)


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


class SKUInProduct(BaseModel):
    """SKU внутри Product (для ответа B2C каталог / seller cabinet)"""
    id: UUID
    name: str
    price: int
    discount: int = 0
    image: Optional[str] = None
    active_quantity: int = Field(..., alias="activeQuantity")
    characteristics: List[CharacteristicValue] = []  # ← без id (для SKU внутри Product)
    
    class Config:
        populate_by_name = True


class ProductImageCreate(BaseModel):
    """Схема для создания изображения товара (POST /products)"""
    url: str = Field(..., description="Ссылка на изображение в S3")
    ordering: int = Field(0, ge=0, description="Порядок отображения")


class ProductImageResponse(BaseModel):
    """Ответ с изображением товара (уже с id — оставляем)"""
    id: UUID
    url: str
    ordering: int