# app/schemas/sku.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.schemas.common import Characteristic, CharacteristicResponse


class SKUImageCreate(BaseModel):
    """Изображение для создания/обновления SKU (по спецификации B2B)"""
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
    """Внутренняя базовая схема SKU (НЕ экспортируется)"""
    name: str = Field(..., min_length=1, max_length=255)
    price: int = Field(..., ge=0, description="Цена в копейках")
    cost_price: Optional[int] = Field(None, ge=0, description="Себестоимость в копейках")
    discount: int = Field(0, ge=0, description="Скидка в копейках")
    article: Optional[str] = Field(None, max_length=100)
    images: List[SKUImageCreate] = Field(default_factory=list)
    characteristics: List[Characteristic] = Field(default_factory=list)  # ← исправлено

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
    """Создание SKU (по спецификации B2B)"""
    product_id: UUID


class SKUUpdate(BaseModel):
    """Обновление SKU (все поля опциональны) (по спецификации B2B)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    price: Optional[int] = Field(None, ge=0)
    cost_price: Optional[int] = Field(None, ge=0)
    discount: Optional[int] = Field(None, ge=0)
    article: Optional[str] = None
    images: Optional[List[SKUImageCreate]] = None
    characteristics: Optional[List[Characteristic]] = None  # ← исправлено

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('name cannot be empty')
        return v.strip() if v else v


class SKUResponse(BaseModel):
    """Полный ответ SKU (seller view) (по спецификации B2B)"""
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
    characteristics: List[CharacteristicResponse] = []  # ← исправлено
    created_at: datetime
    updated_at: datetime  # ← исправлено (обязательное)

    class Config:
        from_attributes = True


class SKUPublicResponse(BaseModel):
    """Публичный SKU (для B2C витрины) (по спецификации B2B)"""
    id: UUID
    product_id: UUID
    name: str
    price: int
    discount: int = 0
    stock_quantity: int
    active_quantity: int
    article: Optional[str] = None
    images: List[SKUImageResponse] = []
    characteristics: List[CharacteristicResponse] = []  # ← исправлено

    class Config:
        from_attributes = True


# SKUInProduct — УДАЛЕН (нет в спецификации B2B)