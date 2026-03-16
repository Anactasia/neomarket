# app/schemas/category.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    image_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class Category(CategoryBase):
    id: int
    level: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Для дерева категорий
    children: List['Category'] = []

    class Config:
        from_attributes = True

# Нужно для рекурсивных ссылок
Category.model_rebuild()