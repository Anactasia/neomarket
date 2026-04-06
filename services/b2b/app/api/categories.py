# app/api/categories.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.category import Category
from app.schemas.category import Category as CategorySchema

router = APIRouter()


def build_category_tree(categories: List[Category], parent_id: Optional[int] = None):
    """Построить дерево категорий"""
    tree = []
    for cat in categories:
        if cat.parent_id == parent_id:
            cat_dict = {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "parent_id": cat.parent_id,
                "level": cat.level,
                "is_active": cat.is_active,
                "children": build_category_tree(categories, cat.id)
            }
            tree.append(cat_dict)
    return tree


# ========== ТОЛЬКО ДЛЯ ЧТЕНИЯ (доступно продавцам) ==========

@router.get("/", response_model=List[CategorySchema])
def get_categories(
    skip: int = 0,
    limit: int = 100,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """
    Получить список всех категорий (плоский список).
    Доступно для чтения продавцам.
    """
    categories = db.query(Category).filter(Category.is_active == is_active).offset(skip).limit(limit).all()
    return categories


@router.get("/tree", response_model=List[CategorySchema])
def get_category_tree(
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """
    Получить дерево категорий.
    Доступно для чтения продавцам.
    """
    categories = db.query(Category).filter(Category.is_active == is_active).all()
    return build_category_tree(categories)


@router.get("/{category_id}", response_model=CategorySchema)
def get_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    """
    Получить категорию по ID.
    Доступно для чтения продавцам.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    return category


# ========== АДМИН-ЭНДПОИНТЫ (только для техподдержки) ==========
# Эти эндпоинты должны быть защищены ролью admin/moderator
# В текущей реализации они закомментированы или вынесены в отдельный роутер

# @router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
# def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
#     """[ADMIN ONLY] Создать новую категорию"""
#     pass

# @router.put("/{category_id}", response_model=CategorySchema)
# def update_category(category_id: int, category_update: CategoryUpdate, db: Session = Depends(get_db)):
#     """[ADMIN ONLY] Обновить категорию"""
#     pass

# @router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_category(category_id: int, db: Session = Depends(get_db)):
#     """[ADMIN ONLY] Удалить категорию"""
#     pass