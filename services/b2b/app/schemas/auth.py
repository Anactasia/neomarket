from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class SellerRegister(BaseModel):
    """Регистрация продавца (адаптировано под вашу модель)"""
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
        if len(v) < 8:  # ← исправлено
            raise ValueError('password must be at least 8 characters')
        return v


class SellerLogin(BaseModel):
    """Логин продавца"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Ответ с токенами"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Обновление токена"""
    refresh_token: str


class SellerResponse(BaseModel):
    """Ответ с данными продавца (по спецификации)"""
    id: UUID
    email: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    company_name: str
    inn: str
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime  # ← добавлено
    
    class Config:
        from_attributes = True