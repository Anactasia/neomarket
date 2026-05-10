"""
Общие Pydantic схемы, переиспользуемые между модулями
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID


class CategoryRef(BaseModel):
    """Ссылка на категорию (для Product)"""
    id: UUID
    name: str


class Image(BaseModel):
    """Изображение товара"""
    url: str
    ordering: int = 0


class ImageResponse(BaseModel):
    """Ответ с изображением (для ProductResponse)"""
    url: str
    ordering: int = 0


class CharacteristicValue(BaseModel):
    """Характеристика товара или SKU (свободные name/value по канону)"""
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
    discount: int = 0  # ← добавить скидку (по канону B2B-2)
    image: Optional[str] = None  # ← основное фото SKU
    active_quantity: int = Field(..., alias="activeQuantity")  # ← исправить название
    characteristics: List[CharacteristicValue] = []
    
    class Config:
        # Позволяет использовать active_quantity как поле при создании
        populate_by_name = True
        # Для совместимости со snake_case и camelCase
        alias_generator = lambda s: ''.join(word.capitalize() if i else word for i, word in enumerate(s.split('_')))


class ProductImageCreate(BaseModel):
    """Схема для создания изображения товара (POST /products)"""
    url: str = Field(..., description="Ссылка на изображение в S3")
    ordering: int = Field(0, ge=0, description="Порядок отображения")


class ProductImageResponse(BaseModel):
    """Ответ с изображением товара"""
    id: UUID
    url: str
    ordering: int