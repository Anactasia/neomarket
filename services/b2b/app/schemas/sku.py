# app/schemas/sku.py
from pydantic import BaseModel, Field, field_validator, computed_field
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.schemas.validators import (
    validate_price,
    validate_quantity,
    validate_compare_price,
    validate_sku_name
)



class SKUBase(BaseModel):
    seller_sku: Optional[str] = Field(None, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    name: str = Field(..., max_length=500)
    price: int = Field(..., description="Цена в копейках")
    compare_at_price: Optional[int] = Field(None)
    quantity: int = Field(0, ge=0, description="Физический остаток")
    reserved_quantity: int = Field(0, ge=0, description="Зарезервировано")  # ← добавить
    is_active: bool = True


# ----- FOR CREATE -----
class SKUCreate(SKUBase):
    product_id: UUID


class SKUCreateWithValidation(SKUCreate):
    """Схема для создания SKU с валидацией"""
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_sku_name(v)
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v: int) -> int:
        return validate_price(v)
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        return validate_quantity(v)
    
    @field_validator('compare_at_price')
    @classmethod
    def validate_compare_at_price(cls, v: Optional[int], info) -> Optional[int]:
        price = info.data.get('price', 0)
        return validate_compare_price(price, v)


# ----- FOR UPDATE -----
class SKUUpdate(BaseModel):
    """Схема для обновления SKU (все поля опциональные)"""
    seller_sku: Optional[str] = Field(None, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=500)
    price: Optional[int] = Field(None)
    compare_at_price: Optional[int] = None
    quantity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class SKUUpdateWithValidation(SKUUpdate):
    """Схема для обновления SKU с валидацией"""
    
    @field_validator('name', check_fields=False)
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_sku_name(v)
        return v
    
    @field_validator('price', check_fields=False)
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            return validate_price(v)
        return v
    
    @field_validator('quantity', check_fields=False)
    @classmethod
    def validate_quantity(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            return validate_quantity(v)
        return v
    
    @field_validator('compare_at_price', check_fields=False)
    @classmethod
    def validate_compare_at_price(cls, v: Optional[int], info) -> Optional[int]:
        if v is not None:
            # При обновлении price может быть в info.data
            price = info.data.get('price')
            if price is not None:
                return validate_compare_price(price, v)
        return v


# ----- FOR RESPONSE -----
class SKU(SKUBase):
    id: UUID
    product_id: UUID
    main_image_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    @computed_field
    @property
    def activeQuantity(self) -> int:
        """Доступно для продажи (по спецификации)"""
        return self.quantity - self.reserved_quantity
    
    class Config:
        from_attributes = True