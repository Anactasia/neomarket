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
    ProductImageResponse,
    CharacteristicValueResponse
)


class ProductStatus(str, Enum):
    CREATED = "CREATED"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    HARD_BLOCKED = "HARD_BLOCKED"


class FieldReport(BaseModel):
    """Замечание по конкретному полю товара или SKU"""
    field_name: str = Field(..., description="Имя поля: title, description, product_images, category, sku_name, sku_image, sku_price")
    sku_id: Optional[UUID] = Field(None, description="ID SKU (null если замечание к товару)")
    comment: str = Field(..., max_length=1000, description="Комментарий модератора")

    class Config:
        from_attributes = True


class BlockingReason(BaseModel):
    """Причина блокировки товара"""
    id: UUID
    title: str = Field(..., description="Текст причины")
    comment: Optional[str] = Field(None, max_length=2000, description="Дополнительный комментарий модератора")

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    category_id: UUID
    images: List[ProductImageCreate] = Field(default_factory=list)
    characteristics: List[CharacteristicValue] = Field(default_factory=list)
    slug: Optional[str] = None
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('title is required')
        return v.strip()
    
    # @field_validator('description')
    # @classmethod
    # def validate_description(cls, v: str) -> str:
    #     if not v or not v.strip():
    #         raise ValueError('description is required')
    #     return v.strip()


class ProductResponse(BaseModel):
    id: UUID
    seller_id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str
    status: ProductStatus
    deleted: bool
    blocked: bool = False
    blocking_reason: Optional[BlockingReason] = None
    field_reports: List[FieldReport] = []
    moderator_comment: Optional[str] = None
    images: List[ProductImageResponse]
    characteristics: List[CharacteristicValueResponse]
    skus: List[SKUInProduct] = []
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