# app/schemas/sku.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.schemas.common import CharacteristicValue, CharacteristicValueResponse


class SKUImageCreate(BaseModel):
    """Изображение для создания/обновления SKU"""
    url: str = Field(..., description="Ссылка на изображение в S3")
    ordering: int = Field(0, description="Порядок отображения")


class SKUImageResponse(BaseModel):
    """Изображение SKU в ответе (по спецификации B2B)"""
    id: UUID
    url: str
    ordering: int

    class Config:
        from_attributes = True


class SKUBase(BaseModel):
    """Базовая схема SKU"""
    name: str = Field(..., min_length=1, max_length=255)
    price: int = Field(..., ge=0, description="Цена в копейках")
    cost_price: Optional[int] = Field(None, ge=0, description="Себестоимость в копейках")
    discount: int = Field(0, ge=0, description="Скидка в копейках")
    article: Optional[str] = Field(None, max_length=100)
    images: List[SKUImageCreate] = Field(default_factory=list)
    characteristics: List[CharacteristicValue] = Field(default_factory=list)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('name is required')
        return v.strip()

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: int) -> int:
        if v < 0:
            raise ValueError('price must be >= 0 (kopecks)')
        return v

    @field_validator('cost_price')
    @classmethod
    def validate_cost_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError('cost_price must be >= 0 (kopecks)')
        return v

    @field_validator('discount')
    @classmethod
    def validate_discount(cls, v: int) -> int:
        if v < 0:
            raise ValueError('discount must be >= 0')
        return v


class SKUCreate(SKUBase):
    """Создание SKU"""
    product_id: UUID


class SKUUpdate(BaseModel):
    """Обновление SKU (все поля опциональны)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    price: Optional[int] = Field(None, ge=0)
    cost_price: Optional[int] = Field(None, ge=0)
    discount: Optional[int] = Field(None, ge=0)
    article: Optional[str] = None
    images: Optional[List[SKUImageCreate]] = None
    characteristics: Optional[List[CharacteristicValue]] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip() if v else v


class SKUResponse(BaseModel):
    """Полный ответ SKU (seller view, с cost_price и reserved_quantity)"""
    id: UUID
    product_id: UUID
    name: str
    price: int
    cost_price: Optional[int] = None
    discount: int = 0
    stock_quantity: int = 0
    active_quantity: int = 0
    reserved_quantity: int = 0
    article: Optional[str] = None
    images: List[SKUImageResponse] = []
    characteristics: List[CharacteristicValueResponse] = []  # ← единый тип
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SKUPublicResponse(BaseModel):
    """Публичный SKU (без cost_price и reserved_quantity, для B2C)"""
    id: UUID
    product_id: UUID
    name: str
    price: int
    discount: int = 0
    stock_quantity: int
    active_quantity: int
    article: Optional[str] = None
    images: List[SKUImageResponse] = []
    characteristics: List[CharacteristicValueResponse] = []

    class Config:
        from_attributes = True


class SKUInProduct(BaseModel):
    """SKU внутри Product (для ответа B2C каталог)"""
    id: UUID
    name: str
    price: int
    discount: int = 0
    images: List[str] = [] 
    active_quantity: int
    characteristics: List[CharacteristicValue] = []

    class Config:
        from_attributes = True
        populate_by_name = True


# Для обратной совместимости
SKU = SKUResponse