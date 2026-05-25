from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.product import Product
from app.models.sku import SKU
from app.schemas.product import (
    ProductPublicShortResponse,
    ProductPublicResponse,
    ProductPublicPaginatedResponse,
    SKUPublicResponse,
    BatchProductIdsRequest,
    ProductStatus
)
from app.api.products import product_to_public_response
import os

router = APIRouter()


def verify_service_key(x_service_key: Optional[str]) -> bool:
    """Проверяет валидность X-Service-Key для межсервисных вызовов"""
    expected_key = os.getenv("B2B_SERVICE_KEY", "b2b-service-key")
    return x_service_key == expected_key


# ───────────────────── PUBLIC CATALOG (для B2C) ─────────────────────

@router.get("/products", response_model=ProductPublicPaginatedResponse)
def get_public_products(
    limit: int = 20,
    offset: int = 0,
    category_id: Optional[UUID] = None,
    search: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    seller_id: Optional[UUID] = None,
    sort: str = "created_desc",
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    Публичный каталог товаров для B2C (витрина).
    
    Авторизация: X-Service-Key (межсервисный вызов)
    Условия видимости:
    - status = MODERATED
    - deleted = false
    - хотя бы один SKU имеет active_quantity > 0
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Валидация sort
    valid_sorts = ["price_asc", "price_desc", "created_desc", "popular"]
    if sort not in valid_sorts:
        sort = "created_desc"
    
    # Фильтр по наличию SKU с остатком через any()
    query = db.query(Product).filter(
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
    )
    
    # Фильтр по категории
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    # Фильтр по продавцу
    if seller_id:
        query = query.filter(Product.seller_id == seller_id)
    
    # Текстовый поиск
    if search:
        query = query.filter(
            (Product.title.ilike(f"%{search}%")) | 
            (Product.description.ilike(f"%{search}%"))
        )
    
    # Фильтры по цене (через any() для SKU)
    if min_price is not None:
        query = query.filter(Product.skus.any(SKU.price >= min_price))
    
    if max_price is not None:
        query = query.filter(Product.skus.any(SKU.price <= max_price))
    
    # Считаем общее количество
    total_count = query.count()
    
    # Сортировка
    if sort == "price_asc":
        # Сортировка по минимальной цене SKU через субзапрос
        min_price_subq = db.query(
            SKU.product_id,
            func.min(SKU.price).label("min_price")
        ).filter(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        ).correlate(Product).as_scalar()
        query = query.order_by(min_price_subq.asc())
    elif sort == "price_desc":
        min_price_subq = db.query(
            SKU.product_id,
            func.min(SKU.price).label("min_price")
        ).filter(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        ).correlate(Product).as_scalar()
        query = query.order_by(min_price_subq.desc())
    elif sort == "created_desc":
        query = query.order_by(Product.created_at.desc())
    elif sort == "popular":
        # Популярность = количество продаж (реализуем как случайную сортировку для MVP)
        # В продакшене: order_by(func.random() или сортировка по количеству заказов)
        query = query.order_by(func.random())
    
    # Пагинация
    products = query.offset(offset).limit(limit).all()
    
    # Формируем ответ
    result_items = []
    for product in products:
        # Получаем минимальную цену среди SKU с остатком
        skus_with_stock = [sku for sku in product.skus if sku.active_quantity > 0]
        min_price_val = min([sku.price for sku in skus_with_stock], default=None)
        
        # Находим главное изображение
        cover_image = None
        if product.images:
            cover_image = product.images[0].url if product.images else None
        
        result_items.append(ProductPublicShortResponse(
            id=product.id,
            title=product.title,
            slug=product.slug or "",
            status=ProductStatus(product.status),
            category_id=product.category_id,
            created_at=product.created_at,
            min_price=min_price_val,
            cover_image=cover_image
        ))
    
    return ProductPublicPaginatedResponse(
        items=result_items,
        total_count=total_count,
        limit=limit,
        offset=offset
    )


@router.post("/products/batch", response_model=List[ProductPublicResponse])
def get_public_products_batch(
    request: BatchProductIdsRequest,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    Batch-запрос публичных карточек товаров по списку ID.
    
    Используется B2C для отображения подборок и избранного.
    Возвращает только видимые товары (без 404 для скрытых).
    
    Авторизация: X-Service-Key
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Получаем товары по ID с фильтрацией видимости
    products = db.query(Product).filter(
        Product.id.in_(request.product_ids),
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False
    ).all()
    
    # Формируем ответ с полными данными
    result = []
    for product in products:
        result.append(product_to_public_response(product, db))
    
    return result


@router.get("/products/{product_id}", response_model=ProductPublicResponse)
def get_public_product(
    product_id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    Публичная карточка товара для витрины.
    
    Авторизация: X-Service-Key
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Получаем товар
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    return product_to_public_response(product, db)


@router.get("/skus/{sku_id}", response_model=SKUPublicResponse)
def get_public_sku(
    sku_id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    Публичный SKU для витрины (без cost_price, reserved_quantity).
    
    Авторизация: X-Service-Key
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Получаем SKU с проверкой видимости товара
    sku = db.query(SKU).join(Product).filter(
        SKU.id == sku_id,
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False
    ).first()
    
    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "SKU not found"}
        )
    
    # Формируем ответ без чувствительных полей
    return SKUPublicResponse(
        id=sku.id,
        product_id=sku.product_id,
        name=sku.name,
        price=sku.price,
        discount=sku.discount,
        stock_quantity=sku.stock_quantity,
        active_quantity=sku.active_quantity,
        article=sku.article,
        images=[],
        characteristics=[]
    )