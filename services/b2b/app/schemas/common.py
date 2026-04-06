# app/schemas/common.py

"""
Общие Pydantic схемы, переиспользуемые между модулями
"""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class CategoryRef(BaseModel):
    """Ссылка на категорию (для Product)"""
    id: int
    name: str


class Image(BaseModel):
    """Изображение товара"""
    url: str
    ordering: int = 0


class CharacteristicValue(BaseModel):
    """Характеристика товара или SKU"""
    name: str
    value: str


class Pagination(BaseModel):
    """Пагинация"""
    limit: int
    offset: int
    total: int


class Error(BaseModel):
    """Стандартный ответ с ошибкой"""
    code: str
    message: str
    details: Optional[dict] = None


class SKUInProduct(BaseModel):
    """SKU внутри Product (для ответа)"""
    id: int
    name: str
    price: int
    activeQuantity: int  # quantity - reserved_quantity
    characteristics: List[CharacteristicValue] = []