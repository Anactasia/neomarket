# app/schemas/sku.py
from pydantic import BaseModel, Field, field_validator, computed_field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.schemas.common import CharacteristicValue


class SKUBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: int = Field(..., ge=1, description="Цена в копейках")
    cost_price: Optional[int] = Field(None, ge=1, description="Себестоимость в копейках")
    discount: int = Field(0, ge=0, description="Скидка в копейках")
    image: Optional[str] = Field(None, description="Ссылка на изображение в S3")
    characteristics: List[CharacteristicValue] = Field(default_factory=list)


# ----- FOR CREATE -----
class SKUCreate(SKUBase):
    product_id: UUID


class SKUCreateWithValidation(SKUCreate):
    """Схема для создания SKU с валидацией"""
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('name is required')
        return v.strip()

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('price must be a positive integer (kopecks)')
        return v
    
    @field_validator('cost_price')
    @classmethod
    def validate_cost_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError('cost_price must be a positive integer (kopecks)')
        return v

    @field_validator('discount')
    @classmethod
    def validate_discount(cls, v: int) -> int:
        if v < 0:
            raise ValueError('discount must be >= 0')
        return v

    @field_validator('image')
    @classmethod
    def validate_image(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            raise ValueError('image is required')
        return v


# ----- FOR UPDATE -----
class SKUUpdate(BaseModel):
    """Схема для обновления SKU (все поля опциональные)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    price: Optional[int] = Field(None, ge=1)
    cost_price: Optional[int] = Field(None, ge=1)
    discount: Optional[int] = Field(None, ge=0)
    image: Optional[str] = None
    characteristics: Optional[List[CharacteristicValue]] = None


class SKUUpdateWithValidation(SKUUpdate):
    """Схема для обновления SKU с валидацией"""

    @field_validator('name', check_fields=False)
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError('name is required')
            return v.strip()
        return v

    @field_validator('price', check_fields=False)
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError('price must be a positive integer (kopecks)')
        return v

    @field_validator('cost_price', check_fields=False)
    @classmethod
    def validate_cost_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError('cost_price must be a positive integer (kopecks)')
        return v

    @field_validator('discount', check_fields=False)
    @classmethod
    def validate_discount(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError('discount must be >= 0')
        return v


# ----- FOR RESPONSE -----
class SKUImageResponse(BaseModel):
    """Изображение SKU в ответе"""
    id: UUID
    url: str
    ordering: int


class SKUCharacteristicResponse(BaseModel):
    """Характеристика SKU в ответе"""
    id: UUID
    name: str
    value: str


class SKU(SKUBase):
    id: UUID
    product_id: UUID
    article: Optional[str] = None
    stock_quantity: int = 0
    active_quantity: int = 0
    reserved_quantity: int = 0
    images: List[SKUImageResponse] = []
    characteristics: List[SKUCharacteristicResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SKUInProduct(BaseModel):
    """SKU внутри Product (для ответа B2C каталог / seller cabinet)"""
    id: UUID
    name: str
    price: int
    discount: int = 0
    image: Optional[str] = None
    active_quantity: int = Field(..., alias="activeQuantity")
    characteristics: List[CharacteristicValue] = []

    class Config:
        populate_by_name = True