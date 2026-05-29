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
from app.models.sku import SKU, SKUImage
from app.schemas.sku import SKU as SKUResponse, SKUImageResponse, SKUCharacteristicResponse
from app.models.sku import SKU, SKUImage, SKUCharacteristic
from app.models.characteristic import Characteristic
from app.models.seller import Seller
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ProductStatus,
    CharacteristicValue,
    Product as ProductSchema,
    BlockingReason,
    FieldReport,
    ProductShortResponse,
    ProductPaginatedResponse,
    ProductPublicShortResponse,
    ProductPublicResponse,
    ProductPublicPaginatedResponse,
    SKUPublicResponse,
    BatchProductIdsRequest,
    ImageAttachRequest,
    ImageUpdateRequest
)
from app.schemas.common import CategoryRef, SKUInProduct, CharacteristicValueResponse, ProductImageResponse
from app.dependencies.auth import get_current_seller, get_current_seller_optional  # ← реальная JWT аутентификация
from app.dependencies.service_keys import verify_moderation_service_key

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 422):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )
def product_to_full_response(product: Product, db: Session) -> ProductResponse:
    """Преобразует Product в полный ProductResponse (с cost_price, reserved_quantity)"""
    
    # Формируем SKU с полными данными
    skus = []
    for sku in product.skus:
        skus.append({
            "id": sku.id,
            "name": sku.name,
            "price": sku.price,
            "cost_price": sku.cost_price,
            "discount": sku.discount or 0,
            "image": sku.images[0].url if sku.images else None,
            "images": [img.url for img in sku.images],
            "active_quantity": sku.active_quantity,
            "reserved_quantity": sku.reserved_quantity,
            "characteristics": [
                CharacteristicValue(
                    name=char.characteristic.name if char.characteristic else "Characteristic",
                    value=char.value_string or ""
                ) for char in sku.characteristics
            ]
        })
    
    return ProductResponse(
        id=product.id,
        seller_id=product.seller_id,
        category_id=product.category_id,
        title=product.title,
        slug=product.slug or "",
        description=product.description or "",
        status=ProductStatus(product.status),
        deleted=product.deleted,  # ← ДОБАВИТЬ
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
            CharacteristicValueResponse(
                id=uuid.uuid4(),
                name=char["name"],
                value=char["value"]
            ) for char in (product.characteristics_json or [])
        ],
        skus=skus,
        created_at=product.created_at,
        updated_at=product.updated_at or product.created_at
    )


def product_to_public_response(product: Product, db: Session) -> ProductPublicResponse:
    """Преобразует Product в публичный ProductPublicResponse"""
    
    # Формируем blocking_reason и field_reports (как у тебя уже есть)
    blocking_reason = None
    if product.blocked and product.blocking_reason_id:
        blocking_reason = BlockingReason(
            id=product.blocking_reason_id,
            title="Товар заблокирован модерацией",
            comment=product.moderation_comment
        )
    
    field_reports = []
    if hasattr(product, 'field_reports_json') and product.field_reports_json:
        for fr in product.field_reports_json:
            field_reports.append(FieldReport(
                field_name=fr.get("field_name", ""),
                sku_id=UUID(fr["sku_id"]) if fr.get("sku_id") else None,
                comment=fr.get("comment", "")
            ))

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
                SKUCharacteristicResponse(
                    id=char.id,
                    name=char.characteristic.name if char.characteristic else "Characteristic",
                    value=char.value_string or ""
                ) for char in sku.characteristics
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
            CharacteristicValueResponse(
                id=uuid.uuid4(),
                name=char["name"],
                value=char["value"]
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
    db: Session,  # ← ДОБАВЛЯЕМ db
    moderation_url: str = "http://moderation:8000",
    event_type: str = "PRODUCT_EDITED",
    json_before: Optional[dict] = None,
    json_after: Optional[dict] = None,
    category_id: Optional[UUID] = None
):
    """
    Сохраняет событие в outbox вместо прямой отправки.
    """
    from datetime import datetime, timezone
    
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
        # для DELETE передаём json_before/json_after как есть
        if json_before:
            payload["json_before"] = json_before
        if json_after:
            payload["json_after"] = json_after
    
    event_payload = {
        "event_type": event_type,
        "idempotency_key": str(idempotency_key),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    
    # Сохраняем в outbox вместо прямой отправки
    save_to_outbox(
        db=db,  
        event_type=event_type,
        target="moderation",
        url=f"{moderation_url}/api/v1/b2b/events",
        payload=event_payload,
        headers={"X-Service-Key": os.getenv("B2B_TO_MOD_KEY", "")}
    )
    

def send_event_to_b2c_sync(
    product_id: UUID, 
    sku_ids: List[UUID],
    idempotency_key: str,
    db: Session,  # ← ДОБАВЛЯЕМ db
    b2c_url: str = "http://b2c:8000",
    event_type: str = "PRODUCT_DELETED"
):
    """
    Сохраняет событие в outbox вместо прямой отправки.
    """
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
    
    # Сохраняем в outbox
    save_to_outbox(
        db=db,
        event_type=event_type,
        target="b2c",
        url=f"{b2c_url}/api/v1/b2b/events",
        payload=event_payload,
        headers={"X-Service-Key": "b2b-to-b2c-key"}
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
        blocked=False,
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
    
    # 6. Формирование ответа (по спецификации neomarket-b2b.yaml)
    return ProductResponse(
        id=db_product.id,
        seller_id=current_seller.id,
        category_id=product.category_id,
        title=db_product.title,
        slug=db_product.slug or "",
        description=db_product.description,
        status=ProductStatus(db_product.status),
        deleted=db_product.deleted,
        blocking_reason_id=db_product.blocking_reason_id,
        moderator_comment=db_product.moderation_comment,
        images=[
            ProductImageResponse(
                id=img.id,
                url=img.url,
                ordering=img.sort_order
            ) for img in db_product.images
        ],
        characteristics=[
            CharacteristicValueResponse(
                id=uuid.uuid4(),
                name=char["name"],
                value=char["value"]
            ) for char in (db_product.characteristics_json or [])
        ],
        skus=[],
        created_at=db_product.created_at,
        updated_at=db_product.updated_at
    )
    
@router.get("/", response_model=ProductPaginatedResponse)
def get_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    search: Optional[str] = None,  # ← добавить для поиска
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Получить список товаров текущего продавца с пагинацией.
    
    IDOR защита: seller_id всегда берётся из JWT токена.
    """
    # Базовый фильтр: только товары текущего продавца
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
    Получить карточку товара.
    
    Режимы вызова:
    1. Seller cabinet (Bearer JWT) — полные данные с cost_price/reserved_quantity
    2. Service call (X-Service-Key) — публичные данные без чувствительных полей
    
    IDOR: при JWT проверяется seller_id, при X-Service-Key — нет
    """
    is_service_call = x_service_key is not None and verify_moderation_service_key(x_service_key)
    
    if is_service_call:
        # Сервисный режим — без проверки seller_id
        product = db.query(Product).options(
            selectinload(Product.skus).selectinload(SKU.images),
            selectinload(Product.skus).selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic),
            selectinload(Product.images),
            selectinload(Product.characteristics)
        ).filter(
            Product.id == product_id,
            Product.deleted == False
        ).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Product not found"}
            )
        return product_to_public_response(product, db)
    else:
        # Seller режим — проверяем seller_id из JWT
        if current_seller is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Authentication required"}
            )
        
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.seller_id == current_seller.id,
            Product.deleted == False
        ).first()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Product not found"}
            )
        
        return product_to_full_response(product, db)
        

@router.patch("/{product_id}", response_model=ProductResponse, status_code=status.HTTP_200_OK)
def update_product(
    product_id: UUID, 
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    # 1. Проверяем существование товара
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # 2. Ownership check (IDOR protection)
    if product.seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"}
        )
    
    # 3. Проверка HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot edit hard-blocked product"}
        )
    
    # 4. Сохраняем старые данные для события
    old_status = product.status
    
    # 5. Обновляем поля
    update_data = product_update.model_dump(exclude_unset=True)
    if update_data:
        for field, value in update_data.items():
            if field == 'characteristics' and value is not None:
                product.characteristics_json = [char.model_dump() for char in value]
            elif field == 'images' and value is not None:
                # Обработка изображений - удаляем старые и добавляем новые
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
    
    # 6. Логика изменения статуса (согласно канону)
    # Если товар в MODERATED или BLOCKED → переводим в ON_MODERATION
    if product.status in [ProductStatus.MODERATED.value, ProductStatus.BLOCKED.value]:
        product.status = ProductStatus.ON_MODERATION.value


        if product.blocked:
            product.blocked = False
            product.blocking_reason_id = None
            product.moderation_comment = None
            # field_reports_json можно оставить для истории или тоже сбросить
            # product.field_reports_json = None
    
    # 7. Отправляем событие EDITED в Moderation (если нужно)
    # Отправляем всегда, кроме случая, когда товар только создан и не блокирован
    should_send_event = (
        product.status != ProductStatus.CREATED.value or 
        product.blocked or
        old_status in [ProductStatus.MODERATED.value, ProductStatus.BLOCKED.value]
    )
    
    print(f"DEBUG: should_send_event={should_send_event}, old_status={old_status}, new_status={product.status}")

    if should_send_event:
        print(f"DEBUG: ВХОДИМ, отправляем PRODUCT_EDITED, product_id={product.id}")
        
        import hashlib

        # Создаём детерминированный ключ на основе данных события
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
        
        # Сохраняем в outbox ПЕРЕД commit
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
        print(f"DEBUG: send_event_to_moderation_sync ВЫЗВАН")
    
    else:
        print(f"DEBUG: НЕ ВХОДИМ, should_send_event=False")
    
    # 8. ВАЖНО: commit после сохранения outbox
    db.commit()
    db.refresh(product)
    product.skus
    
    # 9. Возвращаем обновленный товар
    return product_to_full_response(product, db)
    

@router.get("/{product_id}/skus", response_model=List[SKUResponse])
def list_product_skus(
    product_id: UUID, 
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Все SKU товара (seller view)"""
    product = db.query(Product).options(
        selectinload(Product.skus).selectinload(SKU.images),
        selectinload(Product.skus).selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic)
    ).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    
    if product.seller_id != current_seller.id:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to you"})
    
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
                SKUCharacteristicResponse(
                    id=char.id,
                    name=char.characteristic.name if char.characteristic else "Characteristic",
                    value=char.value_string or ""
                ) for char in sku.characteristics
            ],
            created_at=sku.created_at,
            updated_at=sku.updated_at
        ))
    
    return skus


@router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED)
def add_product_image(
    product_id: UUID, 
    image_data: ImageAttachRequest,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Прикрепить изображение к товару"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    
    if product.seller_id != current_seller.id:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to you"})
    
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
    """Обновить изображение товара (ordering)"""
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
    
    product = db.query(Product).filter(Product.id == image.product_id).first()
    if product.seller_id != current_seller.id:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to you"})
    
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
    """Удалить изображение товара"""
    image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
    
    product = db.query(Product).filter(Product.id == image.product_id).first()
    if product.seller_id != current_seller.id:
        raise HTTPException(status_code=403, detail={"code": "NOT_OWNER", "message": "Product does not belong to you"})
    
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
    Удалить товар (мягкое удаление).
    
    Соответствует US-B2B-04:
    - Мягкое удаление: deleted = True
    - Проверка ownership (IDOR защита)
    - Проверка HARD_BLOCKED → 403
    - Повторное удаление → 400
    - Отправка двух событий: DELETED в Moderation, PRODUCT_DELETED в B2C
    """
    # 1. Проверяем, существует ли товар вообще
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # 2. Проверяем ownership (чужой товар → 403 NOT_OWNER)
    if product.seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"}
        )
    
    # 3. Проверяем HARD_BLOCKED (нельзя удалить HARD_BLOCKED товар)
    if product.status == ProductStatus.HARD_BLOCKED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot delete hard-blocked product"}
        )
    
    # 4. Если товар уже удалён — возвращаем 400
    if product.deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "Product already deleted"}
        )
    
    # 5. Получаем sku_ids для события в B2C
    skus = db.query(SKU).filter(SKU.product_id == product_id).all()
    sku_ids = [sku.id for sku in skus]
    
    # 6. Мягкое удаление
    product.deleted = True
    db.commit()
    db.refresh(product)
    
    # 7. Отправляем событие DELETED в Moderation
    moderation_idempotency_key = uuid_module.uuid4()
    send_event_to_moderation_sync( 
        product_id=product.id,
        seller_id=product.seller_id,
        idempotency_key=moderation_idempotency_key,
        db=db,  # ← передаём db
        event_type="PRODUCT_DELETED",
        json_before={"deleted": False},
        json_after={"deleted": True},
        category_id=product.category_id
    )

    # 8. Отправляем событие PRODUCT_DELETED в B2C
    b2c_idempotency_key = uuid_module.uuid4()
    send_event_to_b2c_sync( 
        product_id=product.id,
        sku_ids=sku_ids,
        idempotency_key=b2c_idempotency_key,
        db=db,  
        event_type="PRODUCT_DELETED"
    )
    
    return None
