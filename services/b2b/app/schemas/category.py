from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=255)
    parent_id: Optional[UUID] = None
    is_active: bool = True

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None

class CategoryResponse(BaseModel):
    """Категория по спецификации"""
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    level: int
    path: List[str]  # ← добавлено
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class CategoryTreeResponse(CategoryResponse):
    children: List['CategoryTreeResponse'] = []

# Нужно для рекурсивных ссылок
CategoryTreeResponse.model_rebuild()