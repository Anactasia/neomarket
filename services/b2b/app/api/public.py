import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_
from typing import List, Optional, Dict
from uuid import UUID
import os

from app.database import get_db
from app.models.product import Product, ProductImage
from app.models.sku import SKU, SKUCharacteristic, SKUImage
from app.schemas.product import (
    ProductPublicShortResponse,
    ProductPublicResponse,
    ProductPublicPaginatedResponse,
    SKUPublicResponse,
    BatchProductIdsRequest,
    ProductStatus,
    BlockingReason,
    FieldReport
)
from app.schemas.sku import SKUImageResponse, SKUPublicResponse as SKUPubResponse
from app.schemas.common import CharacteristicResponse, ProductImageResponse
from app.dependencies.service_keys import verify_b2c_service_key

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


def _extract_characteristic_value(char) -> str:
    """Извлекает значение характеристики в строковом виде"""
    if hasattr(char, 'value_string') and char.value_string:
        return char.value_string
    elif hasattr(char, 'value_int') and char.value_int is not None:
        return str(char.value_int)
    elif hasattr(char, 'value_float') and char.value_float is not None:
        return str(char.value_float)
    elif hasattr(char, 'value_bool') and char.value_bool is not None:
        return str(char.value_bool).lower()
    return ""


def product_to_public_response(product: Product, db: Session) -> ProductPublicResponse:
    """Преобразует Product в публичный ProductPublicResponse (без cost_price/reserved_quantity)"""
    
    # Формируем SKU без чувствительных полей
    skus = []
    for sku in product.skus:
        if sku.active_quantity > 0:  # только доступные SKU
            skus.append(SKUPubResponse(
                id=sku.id,
                product_id=sku.product_id,
                name=sku.name,
                price=sku.price,
                discount=sku.discount or 0,
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
                    CharacteristicResponse(
                        id=char.id,
                        name=char.characteristic.name if char.characteristic else "Unknown",
                        value=_extract_characteristic_value(char)
                    ) for char in sku.characteristics if char.characteristic
                ]
            ))
    
    return ProductPublicResponse(
        id=product.id,
        seller_id=product.seller_id,
        category_id=product.category_id,
        title=product.title,
        slug=product.slug or "",
        description=product.description or "",
        status=ProductStatus(product.status),
        images=[
            ProductImageResponse(
                id=img.id,
                url=img.url,
                ordering=img.sort_order
            ) for img in product.images
        ],
        characteristics=[
            CharacteristicResponse(
                id=char.get("id", uuid.uuid4()),
                name=char.get("name", "Unknown"),
                value=char.get("value", "")
            ) for char in (product.characteristics_json or [])
        ],
        skus=skus,
        created_at=product.created_at,
        updated_at=product.updated_at or product.created_at
    )


# ───────────────────── PUBLIC CATALOG (для B2C) ─────────────────────

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
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Публичный каталог товаров для B2C (витрина) - GET /api/v1/public/products
    
    Авторизация: X-Service-Key (межсервисный вызов)
    
    Фильтр по характеристикам (опционально):
    - filters[color]=red → color=red
    - filters[color]=red,blue → color=red OR color=blue
    - filters[color]=red&filters[size]=L → color=red AND size=L
    """
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    query = db.query(Product).filter(
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
    )
    
    valid_sorts = ["price_asc", "price_desc", "created_desc", "popular"]
    if sort not in valid_sorts:
        sort = "created_desc"
    
    # ========== ФИЛЬТР ПО ХАРАКТЕРИСТИКАМ (ОПЦИОНАЛЬНО) ==========
    # Парсим фильтры из query параметров вида filters[color]=red
    characteristic_filters: Dict[str, List[str]] = {}
    if request:
        for key, value in request.query_params.items():
            if key.startswith("filters[") and key.endswith("]"):
                char_name = key[8:-1]  # 'filters[color]' → 'color'
                # Поддерживаем значения через запятую: red,blue
                values_list = [v.strip() for v in value.split(",")]
                if char_name not in characteristic_filters:
                    characteristic_filters[char_name] = []
                characteristic_filters[char_name].extend(values_list)
    
    # Применяем фильтры по характеристикам (через jsonb_array_elements)
    for char_name, values in characteristic_filters.items():
        if values:
            # Используем EXISTS с jsonb_array_elements для поиска
            from sqlalchemy import text
            conditions = []
            for val in values:
                # Безопасный поиск в JSON массиве
                condition = text(
                    f"EXISTS (SELECT 1 FROM json_array_elements(products.characteristics_json) AS elem "
                    f"WHERE elem->>'name' = '{char_name}' AND elem->>'value' = '{val}')"
                )
                conditions.append(condition)
            if conditions:
                query = query.filter(or_(*conditions))
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if seller_id:
        query = query.filter(Product.seller_id == seller_id)
    
    if search:
        query = query.filter(
            (Product.title.ilike(f"%{search}%")) | 
            (Product.description.ilike(f"%{search}%"))
        )
    
    if min_price is not None:
        query = query.filter(Product.skus.any(SKU.price >= min_price, SKU.active_quantity > 0))
    
    if max_price is not None:
        query = query.filter(Product.skus.any(SKU.price <= max_price, SKU.active_quantity > 0))
    
    total_count = query.count()
    
    # Сортировка
    if sort == "price_asc":
        min_price_subq = db.query(
            func.min(SKU.price).label("min_price")
        ).filter(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        ).correlate(Product).as_scalar()
        query = query.order_by(min_price_subq.asc(), Product.id.desc())
    elif sort == "price_desc":
        min_price_subq = db.query(
            func.min(SKU.price).label("min_price")
        ).filter(
            SKU.product_id == Product.id,
            SKU.active_quantity > 0
        ).correlate(Product).as_scalar()
        query = query.order_by(min_price_subq.desc(), Product.id.desc())
    elif sort == "created_desc":
        query = query.order_by(Product.created_at.desc(), Product.id.desc())
    elif sort == "popular":
        query = query.order_by(func.random(), Product.id.desc())
    
    products = query.options(
        selectinload(Product.skus).selectinload(SKU.images),
        selectinload(Product.skus).selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic),
        selectinload(Product.images)
    ).offset(offset).limit(limit).all()
    
    result_items = []
    for product in products:
        skus_with_stock = [sku for sku in product.skus if sku.active_quantity > 0]
        min_price_val = min([sku.price for sku in skus_with_stock], default=0) if skus_with_stock else 0
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
    """Batch-запрос публичных карточек товаров по списку ID - POST /api/v1/public/products/batch"""
    
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    if len(request.product_ids) > 100:
        error_response("INVALID_REQUEST", "Maximum 100 product IDs per request", 400)
    
    products = db.query(Product).options(
        selectinload(Product.skus).selectinload(SKU.images),
        selectinload(Product.skus).selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic),
        selectinload(Product.images)
    ).filter(
        Product.id.in_(request.product_ids),
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
    ).all()
    
    return [product_to_public_response(product, db) for product in products]


@router.get("/products/{product_id}", response_model=ProductPublicResponse)
def get_public_product(
    product_id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """Публичная карточка товара для витрины - GET /api/v1/public/products/{product_id}"""
    
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    product = db.query(Product).options(
        selectinload(Product.skus).selectinload(SKU.images),
        selectinload(Product.skus).selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic),
        selectinload(Product.images)
    ).filter(
        Product.id == product_id,
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False,
        Product.skus.any(SKU.active_quantity > 0)
    ).first()
    
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    return product_to_public_response(product, db)


@router.get("/products/{product_id}/similar", response_model=List[ProductPublicShortResponse])
def get_public_similar_products(
    product_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """Похожие товары (случайная выборка из той же категории) - GET /api/v1/public/products/{product_id}/similar"""
    
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.status == ProductStatus.MODERATED.value,
        Product.deleted == False
    ).first()
    
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
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
        min_price_val = min([sku.price for sku in skus_with_stock], default=0) if skus_with_stock else 0
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
    """Публичный SKU для витрины (без cost_price, reserved_quantity) - GET /api/v1/public/skus/{sku_id}"""
    
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
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
        error_response("NOT_FOUND", "SKU not found", 404)
    
    return SKUPublicResponse(
        id=sku.id,
        product_id=sku.product_id,
        name=sku.name,
        price=sku.price,
        discount=sku.discount or 0,
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
            CharacteristicResponse(
                id=char.id,
                name=char.characteristic.name if char.characteristic else "Unknown",
                value=_extract_characteristic_value(char)
            ) for char in sku.characteristics if char.characteristic
        ]
    )
