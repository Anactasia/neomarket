# app/schemas/seller.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


# ============================================================
# ПУБЛИЧНЫЕ СХЕМЫ (по спецификации neomarket-b2b.yaml)
# ============================================================

class SellerRegisterRequest(BaseModel):
    """Регистрация продавца (POST /api/v1/auth/register)"""
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


class SellerLoginRequest(BaseModel):
    """Логин продавца (POST /api/v1/auth/login)"""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Обновление токена (POST /api/v1/auth/refresh)"""
    refresh_token: str


class TokenResponse(BaseModel):
    """Ответ с токенами"""
    user_id: UUID
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class SellerUpdateRequest(BaseModel):
    """Обновление профиля продавца (PATCH /api/v1/sellers/me)"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, pattern=r'^\+?[0-9]{10,15}$')


class SellerResponse(BaseModel):
    """Ответ с данными продавца (GET /api/v1/sellers/me)"""
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


# ============================================================
# ВНУТРЕННЯЯ МОДЕЛЬ ДЛЯ БД (отдельно, не для API)
# ============================================================

class SellerDb(BaseModel):
    """Внутренняя модель для БД (НЕ используется в API ответах)"""
    id: UUID
    email: EmailStr
    password_hash: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    company_name: str
    inn: str
    phone: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    status: str = "active"
    rating: Optional[float] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True