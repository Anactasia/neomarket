from fastapi import APIRouter, Depends, HTTPException, status
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


def build_category_tree(categories: List[Category], parent_id: Optional[UUID] = None) -> List[CategoryTreeResponse]:
    """Построить дерево категорий в формате спецификации"""
    tree = []
    for cat in categories:
        if cat.parent_id == parent_id:
            # Вычисляем path (хлебные крошки)
            path = []
            current = cat
            while current.parent_id:
                parent = next((c for c in categories if c.id == current.parent_id), None)
                if parent:
                    path.insert(0, parent.name)
                    current = parent
                else:
                    break
            path.append(cat.name)
            
            tree.append(CategoryTreeResponse(
                id=cat.id,
                name=cat.name,
                parent_id=cat.parent_id,
                level=cat.level,
                path=path,
                is_active=cat.is_active,
                created_at=cat.created_at,
                children=build_category_tree(categories, cat.id)
            ))
    return tree


def build_breadcrumbs(category: Category, db: Session) -> List[CategoryResponse]:
    """Построить цепочку категорий от корня до текущей"""
    breadcrumbs = []
    current = category
    path_names = []
    
    # Собираем имена для path
    temp = current
    while temp:
        path_names.insert(0, temp.name)
        if temp.parent_id:
            temp = db.query(Category).filter(Category.id == temp.parent_id).first()
        else:
            temp = None
    
    # Строим ответ
    temp = category
    while temp:
        breadcrumbs.append(CategoryResponse(
            id=temp.id,
            name=temp.name,
            parent_id=temp.parent_id,
            level=temp.level,
            path=path_names[:temp.level + 1] if path_names else [temp.name],
            is_active=temp.is_active,
            created_at=temp.created_at
        ))
        if temp.parent_id:
            temp = db.query(Category).filter(Category.id == temp.parent_id).first()
        else:
            temp = None
    
    return list(reversed(breadcrumbs))


# ========== ТОЛЬКО ДЛЯ ЧТЕНИЯ (доступно продавцам) ==========

@router.get("/", response_model=List[CategoryResponse])
def get_categories(
    parent_id: Optional[UUID] = None,
    only_root: bool = False,
    is_active: bool = True,
    db: Session = Depends(get_db)
):
    """
    Получить список категорий (плоский список).
    Доступно для чтения продавцам.
    """
    query = db.query(Category).filter(Category.is_active == is_active)
    
    if only_root:
        query = query.filter(Category.parent_id.is_(None))
    elif parent_id is not None:
        query = query.filter(Category.parent_id == parent_id)
    
    categories = query.all()
    
    # Формируем ответ с path
    result = []
    for cat in categories:
        # Вычисляем path
        path = []
        current = cat
        ancestors = []
        while current.parent_id:
            parent = db.query(Category).filter(Category.id == current.parent_id).first()
            if parent:
                ancestors.insert(0, parent.name)
                current = parent
            else:
                break
        path = ancestors + [cat.name]
        
        result.append(CategoryResponse(
            id=cat.id,
            name=cat.name,
            parent_id=cat.parent_id,
            level=cat.level,
            path=path,
            is_active=cat.is_active,
            created_at=cat.created_at
        ))
    
    return result


@router.get("/tree", response_model=List[CategoryTreeResponse])
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


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(
    category_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Получить категорию по ID.
    Доступно для чтения продавцам.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        error_response("NOT_FOUND", "Category not found", 404)
    
    # Вычисляем path
    path = []
    current = category
    ancestors = []
    while current.parent_id:
        parent = db.query(Category).filter(Category.id == current.parent_id).first()
        if parent:
            ancestors.insert(0, parent.name)
            current = parent
        else:
            break
    path = ancestors + [category.name]
    
    return CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        level=category.level,
        path=path,
        is_active=category.is_active,
        created_at=category.created_at
    )


@router.get("/{category_id}/breadcrumbs", response_model=List[CategoryResponse])
def get_category_breadcrumbs(
    category_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Цепочка категорий от корня до текущей.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        error_response("NOT_FOUND", "Category not found", 404)
    
    return build_breadcrumbs(category, db)