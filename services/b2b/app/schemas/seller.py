# app/schemas/seller.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.schemas.validators import (
    validate_inn,
    validate_phone,
    validate_company_name
)


class SellerBase(BaseModel):
    company_name: str = Field(..., max_length=255)
    inn: str = Field(..., max_length=12)
    kpp: Optional[str] = Field(None, max_length=9)
    ogrn: Optional[str] = Field(None, max_length=15)
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None


# ----- FOR CREATE -----
class SellerCreate(SellerBase):
    pass


class SellerCreateWithValidation(SellerCreate):
    """Схема для создания продавца с валидацией"""
    
    @field_validator('company_name')
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        return validate_company_name(v)
    
    @field_validator('inn')
    @classmethod
    def validate_inn(cls, v: str) -> str:
        return validate_inn(v)
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone(v)


# ----- FOR UPDATE -----
class SellerUpdate(BaseModel):
    """Схема для обновления продавца (все поля опциональные)"""
    company_name: Optional[str] = Field(None, max_length=255)
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None


class SellerUpdateWithValidation(SellerUpdate):
    """Схема для обновления продавца с валидацией"""
    
    @field_validator('company_name')
    @classmethod
    def validate_company_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_company_name(v)
        return v
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return validate_phone(v)


# ----- FOR RESPONSE -----
class Seller(SellerBase):
    id: UUID
    status: str
    rating: Optional[float] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True