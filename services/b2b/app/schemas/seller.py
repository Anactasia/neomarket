# app/schemas/seller.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class SellerBase(BaseModel):
    company_name: str = Field(..., max_length=255)
    inn: str = Field(..., max_length=12)
    kpp: Optional[str] = Field(None, max_length=9)
    ogrn: Optional[str] = Field(None, max_length=15)
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None

class SellerCreate(SellerBase):
    pass

class SellerUpdate(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)
    legal_address: Optional[str] = None
    actual_address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None

class Seller(SellerBase):
    id: UUID
    status: str
    rating: Optional[float] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True