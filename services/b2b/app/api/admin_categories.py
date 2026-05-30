from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.models.category import Category
from app.schemas.category import CategoryResponse, CategoryCreate, CategoryUpdate
from app.dependencies.auth import get_current_seller
from app.models.seller import Seller

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


def check_admin(current_seller: Seller):
    if current_seller.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Admin access required"}
        )


def compute_materialized_path(category: Category, db: Session) -> str:
    """Вычисляет materialized path, например 'electronics/smartphones'"""
    path_parts = []
    current = category
    while current:
        path_parts.insert(0, current.name)
        if current.parent_id:
            current = db.query(Category).filter(Category.id == current.parent_id).first()
        else:
            current = None
    return "/".join(path_parts)


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Создать новую категорию"""
    check_admin(current_seller)
    
    level = 0
    if category.parent_id:
        parent = db.query(Category).filter(Category.id == category.parent_id).first()
        if not parent:
            error_response("PARENT_NOT_FOUND", "Parent category not found", 404)
        level = parent.level + 1
    
    db_category = Category(
        name=category.name,
        parent_id=category.parent_id,
        level=level,
        is_active=category.is_active
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    return CategoryResponse(
        id=db_category.id,
        name=db_category.name,
        parent_id=db_category.parent_id,
        level=db_category.level,
        path=compute_materialized_path(db_category, db),
        is_active=db_category.is_active,
        created_at=db_category.created_at
    )


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Обновить категорию"""
    check_admin(current_seller)
    
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        error_response("NOT_FOUND", "Category not found", 404)
    
    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)
    
    db.commit()
    db.refresh(category)
    
    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        level=category.level,
        path=compute_materialized_path(category, db),
        is_active=category.is_active,
        created_at=category.created_at
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Удалить категорию"""
    check_admin(current_seller)
    
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        error_response("NOT_FOUND", "Category not found", 404)
    
    db.delete(category)
    db.commit()
    return None