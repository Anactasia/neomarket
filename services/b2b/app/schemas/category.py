from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class CategoryBase(BaseModel):
    """Внутренняя базовая схема (не экспортируется в API)"""
    name: str = Field(..., max_length=255)
    parent_id: Optional[UUID] = None
    is_active: bool = True


class CategoryCreate(CategoryBase):
    """Создание категории (только админ)"""
    pass


class CategoryUpdate(BaseModel):
    """Обновление категории (по спецификации B2B)"""
    name: Optional[str] = Field(None, max_length=255)
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    """Категория (по спецификации B2B)"""
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    level: int
    path: str = Field(..., description="Materialized path, например electronics/phones")
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryWithChildrenResponse(CategoryResponse):
    """Категория с прямыми подкатегориями (по спецификации B2B)"""
    children: List[CategoryResponse] = []


class CategoryTreeResponse(BaseModel):
    """Дерево категорий (по спецификации B2B)"""
    id: UUID
    name: str
    children: List['CategoryTreeResponse'] = []

    class Config:
        from_attributes = True


# Рекурсивная ссылка
CategoryTreeResponse.model_rebuild()