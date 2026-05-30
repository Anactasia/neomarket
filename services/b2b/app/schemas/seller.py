from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime


# ============================================================
# ПУБЛИЧНЫЕ СХЕМЫ (по спецификации neomarket-b2b.yaml)
# ============================================================

class SellerCreate(BaseModel):
    """Регистрация продавца (POST /api/v1/auth/register)"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    # middle_name — отсутствует в спецификации для SellerCreate
    company_name: str = Field(..., min_length=1, max_length=255)
    inn: str = Field(..., min_length=10, max_length=12)
    phone: Optional[str] = Field(None, pattern=r'^\+?[0-9]{10,15}$')


class LoginRequest(BaseModel):
    """Логин продавца (POST /api/v1/auth/login)"""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Обновление токена (POST /api/v1/auth/refresh)"""
    refresh_token: str


class TokenResponse(BaseModel):
    """Ответ с токенами (по спецификации B2B)"""
    user_id: UUID
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class SellerUpdate(BaseModel):
    """Обновление профиля продавца (PATCH /api/v1/sellers/me)"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, pattern=r'^\+?[0-9]{10,15}$')


class SellerResponse(BaseModel):
    """Ответ с данными продавца (GET /api/v1/sellers/me)"""
    id: UUID
    email: str  # ← string (спецификация: type: string, format: email)
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