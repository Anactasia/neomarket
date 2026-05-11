from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import json
import uuid

from app.database import get_db
from app.models.category import Category
from app.models.product import Product, ProductImage
from app.models.seller import Seller
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ProductStatus,
    CharacteristicValue,
    ImageResponse,
    Product as ProductSchema
)
from app.schemas.common import CategoryRef, SKUInProduct, CharacteristicValueResponse, ProductImageResponse
from app.dependencies.auth import get_current_seller  # ← реальная JWT аутентификация

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Создание карточки товара — B2B-1"""
    
    # 1. Проверка категории
    category = db.query(Category).filter(Category.id == product.category_id).first()
    if not category:
        error_response("INVALID_REQUEST", "Category not found", 400)
    
    # 2. Проверка images
    if not product.images or len(product.images) == 0:
        error_response("INVALID_REQUEST", "At least one image is required", 400)
    
    # 3. Создание товара
    db_product = Product(
        title=product.title,
        description=product.description,
        category_id=product.category_id,
        seller_id=current_seller.id,
        status=ProductStatus.CREATED.value,
        deleted=False,
        blocked=False,
        characteristics_json=[char.model_dump() for char in product.characteristics]
    )
    db.add(db_product)
    db.flush()
    
    # 4. Сохранение изображений
    for img in product.images:
        db_image = ProductImage(
            product_id=db_product.id,
            url=img.url,
            sort_order=img.ordering
        )
        db.add(db_image)
    
    db.commit()
    db.refresh(db_product)
    
    # 5. Формирование ответа (по общей спецификации)
    return ProductResponse(
        id=db_product.id,
        seller_id=current_seller.id,                    # ← добавить
        category_id=product.category_id,                # ← вместо category объекта
        title=db_product.title,
        description=db_product.description,
        status=ProductStatus(db_product.status),
        # deleted и blocked — УДАЛИТЬ
        images=[
            ProductImageResponse(
                id=img.id,                              # ← добавить id
                url=img.url,
                ordering=img.sort_order
            ) for img in db_product.images
        ],
        characteristics=[
            CharacteristicValueResponse(
                id=uuid.uuid4(),                        # ← сгенерировать id
                name=char["name"],
                value=char["value"]
            ) for char in (db_product.characteristics_json or [])
        ],
        skus=[],
        created_at=db_product.created_at,
        updated_at=db_product.updated_at
    )

@router.get("/", response_model=List[ProductSchema])
def get_products(
    skip: int = 0,
    limit: int = 100,
    seller_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)  # ← авторизация для списка товаров
):
    """
    Получить список товаров текущего продавца с фильтрацией.
    seller_id из query игнорируется — всегда фильтруем по текущему продавцу.
    """
    # Всегда фильтруем по текущему продавцу (безопасность)
    query = db.query(Product).filter(Product.seller_id == current_seller.id)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if status:
        query = query.filter(Product.status == status)
    
    # Игнорируем переданный seller_id (защита от IDOR)
    if seller_id:
        # Можно вернуть 400 или просто игнорировать
        pass
    
    products = query.offset(skip).limit(limit).all()
    return products


@router.get("/{product_id}", response_model=ProductSchema)
def get_product(
    product_id: UUID, 
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)  # ← авторизация
):
    """Получить товар по ID (только свои товары)"""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.seller_id == current_seller.id  # ← проверка владельца
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    return product


@router.put("/{product_id}", response_model=ProductSchema)
def update_product(
    product_id: UUID,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)  # ← авторизация
):
    """Обновить товар (только свои товары)"""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.seller_id == current_seller.id  # ← проверка владельца
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    for field, value in product_update.model_dump(exclude_unset=True).items():
        if field == 'characteristics' and value is not None:
            product.characteristics_json = [char.model_dump() for char in value]
        elif value is not None:
            setattr(product, field, value)
    
    # Если обновили важные поля - отправляем на модерацию
    if product_update.model_dump(exclude_unset=True):
        if product.status == ProductStatus.MODERATED.value:
            product.status = ProductStatus.ON_MODERATION.value
    
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID, 
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)  # ← авторизация
):
    """Удалить товар (мягкое удаление)"""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.seller_id == current_seller.id  # ← проверка владельца
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # Мягкое удаление
    product.deleted = True
    db.commit()
    return None