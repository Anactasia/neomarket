from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from typing import List, Optional, Dict
from uuid import UUID
import os

from app.database import get_db
from app.models.product import Product
from app.models.sku import SKU, SKUCharacteristic
from app.schemas.product import (
    ProductPublicShortResponse,
    ProductPublicResponse,
    ProductPublicPaginatedResponse,
    SKUPublicResponse,
    BatchProductIdsRequest,
    ProductStatus
)
from app.schemas.sku import SKUImageResponse, SKUCharacteristicResponse
from app.api.products import product_to_public_response
from app.dependencies.service_keys import verify_b2c_service_key

router = APIRouter()


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
    characteristics: Optional[str] = Query(None, description="Фильтр по характеристикам в формате key=val1,val2&key2=val3"),
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
    
    Фильтр характеристик:
    - Формат: characteristics=colour=red,blue&size=L,M
    - Внутри ключа: OR (red OR blue)
    - Между ключами: AND (colour AND size)
    """
    # 1. Проверка X-Service-Key
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # 2. Базовый запрос (сначала создаём query, потом добавляем фильтры)
    query = db.query(Product).filter(
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
    )
    
    # 3. Валидация sort
    valid_sorts = ["price_asc", "price_desc", "created_desc", "popular"]
    if sort not in valid_sorts:
        sort = "created_desc"
    
    # 4. Фильтр по характеристикам (правильная реализация)
    if characteristics:
        try:
            # Парсим строку характеристик: "colour=red,blue&size=L,M"
            char_filters: Dict[str, List[str]] = {}
            for pair in characteristics.split("&"):
                if "=" in pair:
                    key, values_str = pair.split("=", 1)
                    char_filters[key] = values_str.split(",")
            
            # Для каждого ключа добавляем фильтр
            for char_key, char_values in char_filters.items():
                # Используем JSON операторы PostgreSQL для фильтрации
                from sqlalchemy import text
                
                # Строим условие для каждого значения (OR внутри ключа)
                value_conditions = []
                for val in char_values:
                    value_conditions.append(
                        text(f"jsonb_path_exists(characteristics_json, '$[*] ? (@.name == \"{char_key}\" && @.value == \"{val}\")')")
                    )
                
                # Объединяем через OR
                if value_conditions:
                    from sqlalchemy import or_
                    char_condition = or_(*value_conditions)
                    query = query.filter(char_condition)
                    
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": f"Invalid characteristics format: {str(e)}"}
            )
    
    # 5. Фильтр по категории
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    # 6. Фильтр по продавцу
    if seller_id:
        query = query.filter(Product.seller_id == seller_id)
    
    # 7. Текстовый поиск
    if search:
        query = query.filter(
            (Product.title.ilike(f"%{search}%")) | 
            (Product.description.ilike(f"%{search}%"))
        )
    
    # 8. Фильтры по цене
    if min_price is not None:
        query = query.filter(Product.skus.any(SKU.price >= min_price))
    
    if max_price is not None:
        query = query.filter(Product.skus.any(SKU.price <= max_price))
    
    # 9. Считаем общее количество (до пагинации)
    total_count = query.count()
    
    # 10. Сортировка
    if sort == "price_asc":
        min_price_subq = db.query(
            SKU.product_id,
            func.min(SKU.price).label("min_price")
        ).filter(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        ).correlate(Product).as_scalar()
        query = query.order_by(min_price_subq.asc(), Product.id.desc())
    elif sort == "price_desc":
        min_price_subq = db.query(
            SKU.product_id,
            func.min(SKU.price).label("min_price")
        ).filter(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        ).correlate(Product).as_scalar()
        query = query.order_by(min_price_subq.desc(), Product.id.desc())
    elif sort == "created_desc":
        query = query.order_by(Product.created_at.desc(), Product.id.desc())
    elif sort == "popular":
        # TODO: Реализовать сортировку по популярности (количество продаж)
        # Пока оставляем случайную сортировку как заглушку
        query = query.order_by(func.random(), Product.id.desc())
    
    # 11. Пагинация с предзагрузкой связей
    products = query.options(
        selectinload(Product.skus),
        selectinload(Product.images)
    ).offset(offset).limit(limit).all()
    
    # 12. Формируем ответ
    result_items = []
    for product in products:
        skus_with_stock = [sku for sku in product.skus if sku.active_quantity > 0]
        min_price_val = min([sku.price for sku in skus_with_stock], default=0)
        
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
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Получаем товары по ID с фильтрацией видимости
    products = db.query(Product).options(
        selectinload(Product.skus),
        selectinload(Product.images)
    ).filter(
        Product.id.in_(request.product_ids),
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
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
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Получаем товар
    product = db.query(Product).options(
        selectinload(Product.skus),
        selectinload(Product.images),
        selectinload(Product.characteristics)
    ).filter(
        Product.id == product_id,
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    return product_to_public_response(product, db)


@router.get("/products/{product_id}/similar", response_model=List[ProductPublicShortResponse])
def get_public_similar_products(
    product_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    Похожие товары (случайная выборка из той же категории).
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
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
    
    # Случайная выборка из той же категории, исключая сам товар
    similar = db.query(Product).options(
        selectinload(Product.skus),
        selectinload(Product.images)
    ).filter(
        Product.category_id == product.category_id,
        Product.id != product_id,
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
    ).order_by(func.random()).limit(limit).all()
    
    result = []
    for p in similar:
        skus_with_stock = [sku for sku in p.skus if sku.active_quantity > 0]
        min_price_val = min([sku.price for sku in skus_with_stock], default=0)
        cover_image = p.images[0].url if p.images else None
        
        result.append(ProductPublicShortResponse(
            id=p.id,
            title=p.title,
            slug=p.slug or "",
            status=ProductStatus(p.status),
            category_id=p.category_id,
            created_at=p.created_at,
            min_price=min_price_val,
            cover_image=cover_image
        ))
    
    return result


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
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Получаем SKU с проверкой видимости товара
    sku = db.query(SKU).options(
        selectinload(SKU.images),
        selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic)
    ).join(Product).filter(
        SKU.id == sku_id,
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        SKU.active_quantity > 0
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
        images=[
            SKUImageResponse(
                id=img.id,
                url=img.url,
                ordering=img.sort_order
            ) for img in sku.images
        ],
        characteristics=[
            SKUCharacteristicResponse(
                id=char.id,
                name=char.characteristic.name if char.characteristic else "Characteristic",
                value=char.value_string or ""
            ) for char in sku.characteristics
        ]
    )