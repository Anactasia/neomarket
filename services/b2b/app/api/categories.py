# app/api/categories.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.category import Category
from app.schemas.category import Category as CategorySchema, CategoryCreate, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["Категории"])

def build_category_tree(categories: List[Category], parent_id: Optional[int] = None):
    """Построить дерево категорий"""
    tree = []
    for cat in categories:
        if cat.parent_id == parent_id:
            cat_dict = CategorySchema.from_orm(cat).dict()
            cat_dict["children"] = build_category_tree(categories, cat.id)
            tree.append(cat_dict)
    return tree

@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    """
    Создать новую категорию.
    - **name**: название категории
    - **slug**: URL-идентификатор (уникальный)
    - **parent_id**: ID родительской категории (опционально)
    """
    # Проверяем уникальность slug
    existing = db.query(Category).filter(Category.slug == category.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Категория с таким slug уже существует"
        )
    
    # Вычисляем level
    level = 0
    if category.parent_id:
        parent = db.query(Category).filter(Category.id == category.parent_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Родительская категория не найдена"
            )
        level = parent.level + 1
    
    db_category = Category(**category.dict(), level=level)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.get("/", response_model=List[CategorySchema])
def get_categories(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список всех категорий (плоский список)"""
    categories = db.query(Category).offset(skip).limit(limit).all()
    return categories

@router.get("/tree", response_model=List[CategorySchema])
def get_category_tree(db: Session = Depends(get_db)):
    """Получить дерево категорий"""
    categories = db.query(Category).all()
    return build_category_tree(categories)

@router.get("/{category_id}", response_model=CategorySchema)
def get_category(category_id: int, db: Session = Depends(get_db)):
    """Получить категорию по ID"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    return category

@router.put("/{category_id}", response_model=CategorySchema)
def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db)
):
    """Обновить категорию"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    for field, value in category_update.dict(exclude_unset=True).items():
        setattr(category, field, value)
    
    db.commit()
    db.refresh(category)
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Удалить категорию"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    db.delete(category)
    db.commit()
    return None