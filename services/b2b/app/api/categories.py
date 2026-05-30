from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.category import Category
from app.schemas.category import CategoryResponse, CategoryTreeResponse

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
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


def build_category_tree(categories: List[Category], db: Session, parent_id: Optional[UUID] = None) -> List[CategoryTreeResponse]:
    """Построить дерево категорий (только id, name, children)"""
    tree = []
    for cat in categories:
        if cat.parent_id == parent_id:
            tree.append(CategoryTreeResponse(
                id=cat.id,
                name=cat.name,
                children=build_category_tree(categories, db, cat.id)
            ))
    return tree


@router.get("/", response_model=List[CategoryResponse])
def list_categories(
    parent_id: Optional[UUID] = None,
    only_root: bool = False,
    db: Session = Depends(get_db)
):
    """Публичный список категорий (плоский)"""
    query = db.query(Category).filter(Category.is_active == True)
    
    if only_root:
        query = query.filter(Category.parent_id.is_(None))
    elif parent_id is not None:
        query = query.filter(Category.parent_id == parent_id)
    
    categories = query.all()
    
    result = []
    for cat in categories:
        result.append(CategoryResponse(
            id=cat.id,
            name=cat.name,
            parent_id=cat.parent_id,
            level=cat.level,
            path=compute_materialized_path(cat, db),
            is_active=cat.is_active,
            created_at=cat.created_at
        ))
    
    return result


@router.get("/tree", response_model=List[CategoryTreeResponse])
def get_category_tree(db: Session = Depends(get_db)):
    """Публичное дерево категорий (только id, name, children)"""
    categories = db.query(Category).filter(Category.is_active == True).all()
    return build_category_tree(categories, db)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    db: Session = Depends(get_db)
):
    """Публичная карточка категории"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        error_response("NOT_FOUND", "Category not found", 404)
    
    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        level=category.level,
        path=compute_materialized_path(category, db),
        is_active=category.is_active,
        created_at=category.created_at
    )


@router.get("/{category_id}/breadcrumbs", response_model=List[CategoryResponse])
def get_category_breadcrumbs(
    category_id: UUID,
    db: Session = Depends(get_db)
):
    """Хлебные крошки для категории"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        error_response("NOT_FOUND", "Category not found", 404)
    
    breadcrumbs = []
    current = category
    while current:
        breadcrumbs.insert(0, CategoryResponse(
            id=current.id,
            name=current.name,
            parent_id=current.parent_id,
            level=current.level,
            path=compute_materialized_path(current, db),
            is_active=current.is_active,
            created_at=current.created_at
        ))
        if current.parent_id:
            current = db.query(Category).filter(Category.id == current.parent_id).first()
        else:
            current = None
    
    return breadcrumbs