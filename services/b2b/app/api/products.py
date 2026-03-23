# app/api/products.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.product import Product

from app.schemas.product import (
    Product as ProductSchema,
    ProductCreateWithValidation,
    ProductUpdateWithValidation
)

router = APIRouter(prefix="/products", tags=["Товары"])

@router.post("/", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreateWithValidation, db: Session = Depends(get_db)):
    """
    Создать новый товар.
    - **title**: название товара
    - **slug**: URL-идентификатор (уникальный)
    - **category_id**: ID категории
    - **seller_id**: ID продавца
    """
    # Проверяем уникальность slug
    existing = db.query(Product).filter(Product.slug == product.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Товар с таким slug уже существует"
        )
    
    db_product = Product(**product.dict(), status="DRAFT")
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.get("/", response_model=List[ProductSchema])
def get_products(
    skip: int = 0,
    limit: int = 100,
    seller_id: Optional[str] = None,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Получить список товаров с фильтрацией.
    - **seller_id**: фильтр по продавцу
    - **category_id**: фильтр по категории
    - **status**: фильтр по статусу
    """
    query = db.query(Product)
    
    if seller_id:
        query = query.filter(Product.seller_id == seller_id)
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if status:
        query = query.filter(Product.status == status)
    
    products = query.offset(skip).limit(limit).all()
    return products

@router.get("/{product_id}", response_model=ProductSchema)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Получить товар по ID"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден"
        )
    return product

@router.put("/{product_id}", response_model=ProductSchema)
def update_product(
    product_id: int,
    product_update: ProductUpdateWithValidation,
    db: Session = Depends(get_db)
):
    """Обновить товар"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден"
        )
    
    for field, value in product_update.dict(exclude_unset=True).items():
        setattr(product, field, value)
    
    # Если обновили важные поля - отправляем на модерацию
    if product_update.dict(exclude_unset=True):
        product.status = "DRAFT"
    
    db.commit()
    db.refresh(product)
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Удалить товар"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден"
        )
    
    db.delete(product)
    db.commit()
    return None