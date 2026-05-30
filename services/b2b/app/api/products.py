from fastapi import APIRouter, Depends, HTTPException, status, Header
from app.services.outbox import save_to_outbox
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from typing import List, Optional
from fastapi import Query
from uuid import UUID
import json
import uuid as uuid_module
import uuid
import os

from app.database import get_db
from app.models.category import Category
from app.models.product import Product, ProductImage
from app.models.sku import SKU, SKUImage, SKUCharacteristic
from app.models.characteristic import Characteristic
from app.models.seller import Seller
from app.schemas.sku import SKUResponse, SKUPublicResponse, SKUImageResponse
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ProductStatus,
    BlockingReason,
    FieldReport,
    ProductShortResponse,
    ProductPaginatedResponse,
    ProductPublicShortResponse,
    ProductPublicResponse,
    ProductPublicPaginatedResponse,
    BatchProductIdsRequest,
    ImageAttachRequest,
    ImageUpdateRequest
)
from app.schemas.common import CategoryRef, CharacteristicResponse, ProductImageResponse
from app.dependencies.auth import get_current_seller, get_current_seller_optional
from app.dependencies.service_keys import verify_moderation_service_key

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


def product_to_full_response(product: Product, db: Session) -> ProductResponse:
    """Преобразует Product в полный ProductResponse (с cost_price, reserved_quantity)"""
    
    skus = []
    for sku in product.skus:
        skus.append(SKUResponse(
            id=sku.id,
            product_id=sku.product_id,
            name=sku.name,
            price=sku.price,
            cost_price=sku.cost_price,
            discount=sku.discount or 0,
            stock_quantity=sku.stock_quantity,
            active_quantity=sku.active_quantity,
            reserved_quantity=sku.reserved_quantity,
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
            ],
            created_at=sku.created_at,
            updated_at=sku.updated_at or sku.created_at
        ))
    
    return ProductResponse(
        id=product.id,
        seller_id=product.seller_id,
        category_id=product.category_id,
        title=product.title,
        slug=product.slug or "",
        description=product.description or "",
        status=ProductStatus(product.status),
        deleted=product.deleted,
        blocking_reason_id=product.blocking_reason_id,
        moderator_comment=product.moderation_comment,
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


def product_to_public_response(product: Product, db: Session) -> ProductPublicResponse:
    """Преобразует Product в публичный ProductPublicResponse (без cost_price/reserved_quantity)"""
    
    # Формируем SKU без чувствительных полей
    skus = []
    for sku in product.skus:
        skus.append(SKUPublicResponse(
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
                id=uuid.uuid4(),
                name=char.get("name", "Unknown"),
                value=char.get("value", "")
            ) for char in (product.characteristics_json or [])
        ],
        skus=skus,
        created_at=product.created_at,
        updated_at=product.updated_at or product.created_at
    )

    
def send_event_to_moderation_sync(
    product_id: UUID,
    seller_id: UUID,
    idempotency_key: str,
    db: Session,
    moderation_url: str = "http://moderation:8000",
    event_type: str = "PRODUCT_EDITED",
    json_before: Optional[dict] = None,
    json_after: Optional[dict] = None,
    category_id: Optional[UUID] = None
):
    """Сохраняет событие в outbox (формат соответствует canon)."""
    from datetime import datetime, timezone
    
    # Маппинг event_type в canon (по спецификации Moderation)
    event_map = {
        "PRODUCT_CREATED": "CREATED",
        "PRODUCT_EDITED": "EDITED",
        "SKU_EDITED": "EDITED",
        "PRODUCT_DELETED": "DELETED",
    }
    canon_event = event_map.get(event_type, "UNKNOWN")
    
    payload: dict = {
        "product_id": str(product_id),
        "seller_id": str(seller_id),
    }
    if category_id:
        payload["category_id"] = str(category_id)
    
    if event_type == "PRODUCT_CREATED":
        payload["json_after"] = json_after or {}
    elif event_type == "PRODUCT_EDITED":
        payload["json_before"] = json_before or {}
        payload["json_after"] = json_after or {}
    elif event_type == "PRODUCT_DELETED":
        if json_before:
            payload["json_before"] = json_before
        if json_after:
            payload["json_after"] = json_after
    
    # Формат события по canon
    event_payload = {
        "event": canon_event,  # ← изменено с event_type
        "idempotency_key": str(idempotency_key),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    
    save_to_outbox(
        db=db,
        event_type=event_type,  # сохраняем оригинальный тип для фильтрации
        target="moderation",
        url=f"{moderation_url}/api/v1/b2b/events",
        payload=event_payload,
        headers={"X-Service-Key": os.getenv("B2B_TO_MOD_KEY", "")}
    )
    

def send_event_to_b2c_sync(
    product_id: UUID, 
    sku_ids: List[UUID],
    idempotency_key: str,
    db: Session,
    b2c_url: str = "http://b2c:8000",
    event_type: str = "PRODUCT_DELETED"
):
    """Сохраняет событие в outbox вместо прямой отправки."""
    from datetime import datetime, timezone
    
    payload = {
        "product_id": str(product_id),
        "sku_ids": [str(sku_id) for sku_id in sku_ids]
    }
    
    event_payload = {
        "event_type": event_type,
        "idempotency_key": str(idempotency_key),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    
    save_to_outbox(
        db=db,
        event_type=event_type,
        target="b2c",
        url=f"{b2c_url}/api/v1/b2b/events",
        payload=event_payload,
        headers={"X-Service-Key": os.getenv("B2B_TO_B2C_KEY", "b2b-to-b2c-key")}
    )
    

# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Создание карточки товара - POST /api/v1/products/"""
    
    # 1. Проверка категории
    category = db.query(Category).filter(Category.id == product.category_id).first()
    if not category:
        error_response("INVALID_REQUEST", "Category not found", 400)
    
    if not category.is_active:
        error_response("INVALID_REQUEST", "Category is not active", 400)
    
    # 2. Проверка images
    if not product.images or len(product.images) == 0:
        error_response("INVALID_REQUEST", "At least one image is required", 400)
    
    # 3. Генерация slug из title, если не передан
    slug = product.slug
    if not slug:
        slug = product.title.lower().replace(' ', '-')[:50]
    
    # 4. Создание товара
    db_product = Product(
        title=product.title,
        slug=slug,
        description=product.description,
        category_id=product.category_id,
        seller_id=current_seller.id,
        status=ProductStatus.CREATED.value,
        deleted=False,
        moderation_comment=None,
        blocking_reason_id=None,
        characteristics_json=[char.model_dump() for char in product.characteristics]
    )
    db.add(db_product)
    db.flush()
    
    # 5. Сохранение изображений
    for img in product.images:
        db_image = ProductImage(
            product_id=db_product.id,
            url=img.url,
            sort_order=img.ordering
        )
        db.add(db_image)
    
    db.commit()
    db.refresh(db_product)
    
    return product_to_full_response(db_product, db)
    

@router.get("/", response_model=ProductPaginatedResponse)
def get_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    search: Optional[str] = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Получить список товаров текущего продавца с пагинацией - GET /api/v1/products/
    
    IDOR защита: seller_id всегда берётся из JWT токена.
    """
    query = db.query(Product).filter(Product.seller_id == current_seller.id)

    if status:
        query = query.filter(Product.status == status)
    if not include_deleted:
        query = query.filter(Product.deleted == False)
    if search:
        query = query.filter(Product.title.ilike(f"%{search}%"))

    total_count = query.count()
    products = query.options(
        selectinload(Product.skus),
        selectinload(Product.images)
    ).offset(offset).limit(limit).all()
    
    items = []
    for product in products:
        skus = product.skus  
        min_price = min([sku.price for sku in skus], default=0) if skus else 0
        cover_image = product.images[0].url if product.images else None
        
        items.append(ProductShortResponse(
            id=product.id,
            title=product.title,
            slug=product.slug or "",
            status=ProductStatus(product.status),
            category_id=product.category_id,
            deleted=product.deleted,
            created_at=product.created_at,
            min_price=min_price,
            cover_image=cover_image
        ))
    
    return ProductPaginatedResponse(
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db),
    current_seller: Optional[Seller] = Depends(get_current_seller_optional)
):
    """
    Получить карточку товара - GET /api/v1/products/{product_id}
    
    Режимы вызова:
    1. Seller cabinet (Bearer JWT) — полные данные с cost_price/reserved_quantity
    2. Service call (X-Service-Key) — публичные данные без чувствительных полей
    
    IDOR: при JWT проверяется seller_id, при X-Service-Key — нет
    """
    is_service_call = x_service_key is not None and verify_moderation_service_key(x_service_key)
    
    if is_service_call:
        product = db.query(Product).options(
            selectinload(Product.skus).selectinload(SKU.images),
            selectinload(Product.skus).selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic),
            selectinload(Product.images)
        ).filter(
            Product.id == product_id,
            Product.deleted == False
        ).first()
        if not product:
            error_response("NOT_FOUND", "Product not found", 404)
        return product_to_public_response(product, db)
    else:
        if current_seller is None:
            error_response("UNAUTHORIZED", "Authentication required", 401)
        
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.seller_id == current_seller.id,
            Product.deleted == False
        ).first()
        
        if not product:
            error_response("NOT_FOUND", "Product not found", 404)
        
        return product_to_full_response(product, db)
        

@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID, 
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Обновление товара - PATCH /api/v1/products/{product_id}"""
    
    # 1. Проверяем существование товара
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    # 2. Ownership check (IDOR protection)
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Product does not belong to the authenticated seller", 403)
    
    # 3. Проверка HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED.value:
        error_response("FORBIDDEN", "Cannot edit hard-blocked product", 403)
    
    # 4. Сохраняем старые данные для события
    old_status = product.status
    
    # 5. Обновляем поля
    update_data = product_update.model_dump(exclude_unset=True)
    if update_data:
        for field, value in update_data.items():
            if field == 'characteristics' and value is not None:
                product.characteristics_json = [char.model_dump() for char in value]
            elif field == 'images' and value is not None:
                db.query(ProductImage).filter(ProductImage.product_id == product.id).delete()
                for img in value:
                    db_image = ProductImage(
                        product_id=product.id,
                        url=img.url,
                        sort_order=img.ordering
                    )
                    db.add(db_image)
            elif value is not None:
                setattr(product, field, value)
    
    # 6. Логика изменения статуса
    if product.status in [ProductStatus.MODERATED.value, ProductStatus.BLOCKED.value]:
        product.status = ProductStatus.ON_MODERATION.value
        if hasattr(product, 'blocked') and product.blocked:
            product.blocked = False
            product.blocking_reason_id = None
            product.moderation_comment = None
    
    # 7. Сохраняем изменения (flush, не commit)
    db.flush()
    
    # 8. Отправляем событие EDITED в Moderation (ДО commit)
    should_send_event = (
        product.status != ProductStatus.CREATED.value or 
        (hasattr(product, 'blocked') and product.blocked) or
        old_status in [ProductStatus.MODERATED.value, ProductStatus.BLOCKED.value]
    )

    if should_send_event:
        key_string = f"{product.id}:PRODUCT_EDITED:{old_status}:{product.status}"
        idempotency_key = str(uuid_module.uuid5(uuid_module.NAMESPACE_DNS, key_string))
        
        json_before = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": old_status,
            "description": product.description,
            "category_id": str(product.category_id) if product.category_id else None
        }
        
        json_after = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": product.status,
            "description": product.description,
            "category_id": str(product.category_id) if product.category_id else None
        }
        
        send_event_to_moderation_sync(
            product_id=product.id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            db=db,
            event_type="PRODUCT_EDITED",
            json_before=json_before,
            json_after=json_after,
            category_id=product.category_id
        )
    
    # 9. Commit ПОСЛЕ отправки события
    db.commit()
    db.refresh(product)
    
    return product_to_full_response(product, db)
    

@router.get("/{product_id}/skus", response_model=List[SKUResponse])
def list_product_skus(
    product_id: UUID, 
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Все SKU товара (seller view) - GET /api/v1/products/{product_id}/skus"""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Product does not belong to you", 403)
    
    skus = db.query(SKU).options(
        selectinload(SKU.images),
        selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic)
    ).filter(SKU.product_id == product_id).all()
    
    result = []
    for sku in skus:
        result.append(SKUResponse(
            id=sku.id,
            product_id=sku.product_id,
            name=sku.name,
            price=sku.price,
            cost_price=sku.cost_price,
            discount=sku.discount or 0,
            stock_quantity=sku.stock_quantity,
            active_quantity=sku.active_quantity,
            reserved_quantity=sku.reserved_quantity,
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
            ],
            created_at=sku.created_at,
            updated_at=sku.updated_at or sku.created_at
        ))
    
    return result


# ========== ИЗОБРАЖЕНИЯ ТОВАРОВ ==========

@router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED)
def add_product_image(
    product_id: UUID, 
    image_data: ImageAttachRequest,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Прикрепить изображение к товару - POST /api/v1/products/{product_id}/images"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Product does not belong to you", 403)
    
    db_image = ProductImage(
        product_id=product_id,
        url=image_data.url or "",
        sort_order=image_data.ordering
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    return ProductImageResponse(
        id=db_image.id,
        url=db_image.url,
        ordering=db_image.sort_order
    )
    

@router.patch("/images/{image_id}", response_model=ProductImageResponse)
def update_product_image(
    image_id: UUID,
    image_data: ImageUpdateRequest,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Обновить изображение товара - PATCH /api/v1/products/images/{image_id}"""
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        error_response("NOT_FOUND", "Image not found", 404)
    
    product = db.query(Product).filter(Product.id == image.product_id).first()
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Product does not belong to you", 403)
    
    if image_data.url is not None:
        image.url = image_data.url
    if image_data.ordering is not None:
        image.sort_order = image_data.ordering
    
    db.commit()
    db.refresh(image)
    
    return ProductImageResponse(
        id=image.id,
        url=image.url,
        ordering=image.sort_order
    )


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Удалить изображение товара - DELETE /api/v1/products/images/{image_id}"""
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        error_response("NOT_FOUND", "Image not found", 404)
    
    product = db.query(Product).filter(Product.id == image.product_id).first()
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Product does not belong to you", 403)
    
    db.delete(image)
    db.commit()
    return None


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID, 
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Удалить товар (мягкое удаление) - DELETE /api/v1/products/{product_id}
    
    - Мягкое удаление: deleted = True
    - Проверка ownership (IDOR защита)
    - Проверка HARD_BLOCKED → 403
    - Повторное удаление → 400
    - Отправка двух событий: DELETED в Moderation, PRODUCT_DELETED в B2C
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Product does not belong to the authenticated seller", 403)
    
    if product.status == ProductStatus.HARD_BLOCKED.value:
        error_response("FORBIDDEN", "Cannot delete hard-blocked product", 403)
    
    if product.deleted:
        error_response("INVALID_REQUEST", "Product already deleted", 400)
    
    skus = db.query(SKU).filter(SKU.product_id == product_id).all()
    sku_ids = [sku.id for sku in skus]
    
    product.deleted = True
    db.flush()  # ← вместо commit
    
    # Отправка событий (ДО commit)
    moderation_idempotency_key = uuid_module.uuid4()
    send_event_to_moderation_sync( 
        product_id=product.id,
        seller_id=product.seller_id,
        idempotency_key=moderation_idempotency_key,
        db=db,
        event_type="PRODUCT_DELETED",
        json_before={"deleted": False},
        json_after={"deleted": True},
        category_id=product.category_id
    )

    b2c_idempotency_key = uuid_module.uuid4()
    send_event_to_b2c_sync( 
        product_id=product.id,
        sku_ids=sku_ids,
        idempotency_key=b2c_idempotency_key,
        db=db,
        event_type="PRODUCT_DELETED"
    )
    
    # Commit ПОСЛЕ отправки событий
    db.commit()
    db.refresh(product)
    
    return None