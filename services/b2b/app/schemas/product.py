from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.schemas.common import (
    CategoryRef, 
    ImageResponse, 
    CharacteristicValue, 
    SKUInProduct,
    ProductImageCreate,
    ProductImageResponse
)


class ProductStatus(str, Enum):
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    HARD_BLOCKED = "HARD_BLOCKED"


class ProductCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=5000)
    category_id: UUID
    images: List[ProductImageCreate] = Field(..., min_length=1)
    characteristics: List[CharacteristicValue] = Field(default_factory=list)
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('title is required')
        return v.strip()
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('description is required')
        return v.strip()


class ProductResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: ProductStatus
    deleted: bool = False
    blocked: bool = False
    category: CategoryRef
    images: List[ImageResponse] = Field(default_factory=list)
    characteristics: List[CharacteristicValue] = Field(default_factory=list)
    skus: List[SKUInProduct] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    characteristics: Optional[List[CharacteristicValue]] = None


class Product(BaseModel):
    id: UUID
    seller_id: UUID
    status: str
    title: str
    description: Optional[str] = None
    category_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True