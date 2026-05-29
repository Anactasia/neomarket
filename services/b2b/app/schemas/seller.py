from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.schemas.validators import (
    validate_inn,
    validate_phone,
    validate_company_name
)


# ============================================================
# ВНУТРЕННИЕ СХЕМЫ (для БД и внутреннего использования)
# ============================================================

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


# ----- ВНУТРЕННЯЯ МОДЕЛЬ (для БД) -----
class Seller(SellerBase):
    """Внутренняя модель продавца (для БД)"""
    id: UUID
    status: str
    rating: Optional[float] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================
# ПУБЛИЧНЫЕ СХЕМЫ (по спецификации neomarket-b2b.yaml)
# ============================================================

class SellerResponse(BaseModel):
    """Ответ с данными продавца по спецификации OpenAPI"""
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    company_name: str
    inn: str
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SellerRegisterRequest(BaseModel):
    """Запрос на регистрацию продавца (по спецификации)"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    company_name: str = Field(..., min_length=1, max_length=255)
    inn: str = Field(..., min_length=10, max_length=12)
    phone: Optional[str] = Field(None, pattern=r'^\+?[0-9]{10,15}$')
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('password must be at least 8 characters')
        return v