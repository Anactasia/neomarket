from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import json
import uuid as uuid_module
import uuid
import os
from app.database import get_db
from app.models.category import Category
from app.models.product import Product, ProductImage
from app.models.sku import SKU
from app.models.seller import Seller
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    ProductStatus,
    CharacteristicValue,
    ImageResponse,
    Product as ProductSchema,
    BlockingReason,
    FieldReport
)
from app.schemas.common import CategoryRef, SKUInProduct, CharacteristicValueResponse, ProductImageResponse
from app.dependencies.auth import get_current_seller, get_current_seller_optional  # ← реальная JWT аутентификация

router = APIRouter()

def verify_service_key(x_service_key: Optional[str]) -> bool:
    """Проверяет валидность X-Service-Key для межсервисных вызовов"""
    expected_key = os.getenv("B2B_SERVICE_KEY", "b2b-service-key")
    return x_service_key == expected_key



def error_response(code: str, message: str, status_code: int = 422):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )
def product_to_full_response(product: Product, db: Session) -> ProductResponse:
    """Преобразует Product в полный ProductResponse (с cost_price, reserved_quantity)"""
    # Формируем blocking_reason
    blocking_reason = None
    if product.blocked and product.blocking_reason_id:
        blocking_reason = BlockingReason(
            id=product.blocking_reason_id,
            title="Товар заблокирован модерацией",
            comment=product.moderation_comment
        )
    
    # Формируем field_reports
    field_reports = []
    if hasattr(product, 'field_reports_json') and product.field_reports_json:
        for fr in product.field_reports_json:
            field_reports.append(FieldReport(
                field_name=fr.get("field_name", ""),
                sku_id=UUID(fr["sku_id"]) if fr.get("sku_id") else None,
                comment=fr.get("comment", "")
            ))
    
    # Формируем SKU с полными данными
    skus = []
    for sku in product.skus:
        skus.append(SKUInProduct(
            id=sku.id,
            name=sku.name,
            price=sku.price,
            cost_price=sku.cost_price or 0,
            discount=sku.discount or 0,
            image=sku.image or "",
            active_quantity=sku.active_quantity,
            reserved_quantity=sku.reserved_quantity,
            characteristics=[]
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
        blocked=product.blocked,
        blocking_reason=blocking_reason,
        field_reports=field_reports,
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
        updated_at=product.updated_at
    )


def product_to_public_response(product: Product, db: Session) -> ProductResponse:
    """Преобразует Product в публичный ProductResponse (без cost_price, reserved_quantity)"""
    # Формируем SKU без чувствительных полей
    skus = []
    for sku in product.skus:
        skus.append(SKUInProduct(
            id=sku.id,
            name=sku.name,
            price=sku.price,
            cost_price=None,  # не показываем
            discount=sku.discount or 0,
            image=sku.image or "",
            active_quantity=sku.active_quantity,
            reserved_quantity=None,  # не показываем
            characteristics=[]
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
        blocked=product.blocked,
        blocking_reason=None,  # в публичном режиме не показываем
        field_reports=[],  # в публичном режиме не показываем
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
        updated_at=product.updated_at
    )

def send_event_to_moderation_sync(
    product_id: UUID, 
    seller_id: UUID,
    idempotency_key: str,
    moderation_url: str = "http://moderation:8000",
    event_type: str = "PRODUCT_EDITED",
    json_before: Optional[dict] = None,
    json_after: Optional[dict] = None,
    category_id: Optional[UUID] = None
):
    """
    Отправляет событие (PRODUCT_CREATED или PRODUCT_EDITED) в Moderation Service синхронно.
    Для production рекомендуется outbox pattern или асинхронная очередь.
    
    Соответствует спецификации neomarket-moderation.yaml:
    - URL: POST /api/v1/b2b/events
    - Тело: IncomingB2BEvent (event_type, idempotency_key, occurred_at, payload)
    
    event_type: "PRODUCT_CREATED" или "PRODUCT_EDITED"
    payload:
      - PRODUCT_CREATED: {product_id, seller_id, category_id?, json_after}
      - PRODUCT_EDITED: {product_id, seller_id, category_id?, json_before, json_after}
    """
    import httpx
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    
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
    
    event_payload = {
        "event_type": event_type,
        "idempotency_key": str(idempotency_key),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{moderation_url}/api/v1/b2b/events",
                json=event_payload,
                headers={"X-Service-Key": "b2b-service-key"}
            )
    except Exception as e:
        # fire-and-forget: не блокируем ответ при недоступности Moderation
        # Но логируем потерю события для advisory
        logger.warning(
            f"Failed to send {event_type} event to Moderation Service: {e}. "
            f"Event lost: product_id={product_id}, idempotency_key={idempotency_key}"
        )
    

def send_event_to_b2c_sync(
    product_id: UUID, 
    sku_ids: List[UUID],
    idempotency_key: str,
    b2c_url: str = "http://b2c:8000",
    event_type: str = "PRODUCT_DELETED"
):
    """
    Отправляет событие (PRODUCT_DELETED, PRODUCT_BLOCKED и т.п.) в B2C Service.
    
    Соответствует спецификации neomarket-b2c.yaml:
    - URL: POST /api/v1/b2b/events
    - Тело: B2BEvent (event_type, idempotency_key, occurred_at, payload)
    
    event_type: "PRODUCT_DELETED", "PRODUCT_BLOCKED", "PRODUCT_HARD_BLOCKED", ...
    payload:
      - PRODUCT_DELETED: {product_id}
    """
    import httpx
    from datetime import datetime, timezone
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Payload соответствует EventProductRef для PRODUCT_DELETED
    payload = {
        "product_id": str(product_id)
    }
    
    event_payload = {
        "event_type": event_type,
        "idempotency_key": str(idempotency_key),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{b2c_url}/api/v1/b2b/events",
                json=event_payload,
                headers={"X-Service-Key": "b2b-to-b2c-key"}
            )
    except Exception as e:
        logger.warning(
            f"Failed to send {event_type} event to B2C Service: {e}. "
            f"Event lost: product_id={product_id}, idempotency_key={idempotency_key}"
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
    
@router.get("/", response_model=List[ProductSchema])
def get_products(
    skip: int = 0,
    limit: int = 100,
    seller_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    status: Optional[str] = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)  # ← авторизация для списка товаров
):
    """
    Получить список товаров текущего продавца с фильтрацией.
    seller_id из query игнорируется — всегда фильтруем по текущему продавцу.
    Удалённые товары не включаются по умолчанию (include_deleted=false).
    """
    # Всегда фильтруем по текущему продавцу (безопасность)
    query = db.query(Product).filter(Product.seller_id == current_seller.id)

    if category_id:
        query = query.filter(Product.category_id == category_id)
    if status:
        query = query.filter(Product.status == status)
    if not include_deleted:
        query = query.filter(Product.deleted == False)

    # Игнорируем переданный seller_id (защита от IDOR)
    if seller_id:
        # Можно вернуть 400 или просто игнорировать
        pass
    
    products = query.offset(skip).limit(limit).all()
    return products


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db),
    current_seller: Optional[Seller] = Depends(get_current_seller_optional)  # новый dependency
):
    """
    Получить карточку товара.
    
    Режимы вызова:
    1. Seller cabinet (Bearer JWT) — полные данные с cost_price/reserved_quantity
    2. Service call (X-Service-Key) — публичные данные без чувствительных полей
    
    IDOR: при JWT проверяется seller_id, при X-Service-Key — нет
    """
    is_service_call = x_service_key is not None and verify_service_key(x_service_key)
    
    # Определяем, какой режим используем
    if is_service_call:
        # Сервисный режим — без проверки seller_id
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Product not found"}
            )
        # Возвращаем публичные данные
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
            Product.seller_id == current_seller.id
        ).first()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Product not found"}
            )
        
        # Возвращаем полные данные
        return product_to_full_response(product, db)
    

@router.patch("/{product_id}", response_model=ProductResponse, status_code=status.HTTP_200_OK)
def update_product(
    product_id: UUID, 
    product_update: ProductUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    # 1. Проверяем, существует ли товар вообще
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # 2. Проверяем ownership (чужой товар → 403)
    if product.seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Product does not belong to you"}
        )
    
    # 3. Проверяем HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED.value:
        error_response("FORBIDDEN", "Cannot edit hard-blocked product", 403)
    
    # 3. Обновляем поля
    update_data = product_update.model_dump(exclude_unset=True)
    if update_data:
        for field, value in update_data.items():
            if field == 'characteristics' and value is not None:
                product.characteristics_json = [char.model_dump() for char in value]
            elif value is not None:
                setattr(product, field, value)
    
    # 4. Проверяем, нужно ли менять статус товара
    # Статус меняется, если товар был в MODERATED или BLOCKED
    needs_status_change = product.status in [ProductStatus.MODERATED.value, ProductStatus.BLOCKED.value]
    
    # 5. Если товар в MODERATED или BLOCKED → меняем статус на ON_MODERATION
    if needs_status_change:
        product.status = ProductStatus.ON_MODERATION.value
    
    db.commit()
    db.refresh(product)
    
    # 6. Отправляем событие EDITED в Moderation (background task)
    # Событие отправляется всегда, если товар уже был на модерации (статус != CREATED)
    # или если он в BLOCKED (что означает, что был на модерации ранее)
    if product.status != ProductStatus.CREATED.value or product.blocked:
        import uuid as uuid_module
        idempotency_key = uuid_module.uuid4()
        # Формируем json_before и json_after
        json_before = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": ProductStatus.MODERATED.value if needs_status_change else product.status
        }
        json_after = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": ProductStatus.ON_MODERATION.value if needs_status_change else product.status
        }
        background_tasks.add_task(
            send_event_to_moderation_sync,
            product_id=product.id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            event_type="PRODUCT_EDITED",
            json_before=json_before,
            json_after=json_after,
            category_id=product.category_id
        )
    
    # Формируем ответ с реальными данными из БД
    # Загружаем SKUs из БД
    skus = [
        SKUInProduct(
            id=sku.id,
            name=sku.name,
            price=sku.price,
            discount=sku.discount,
            image=sku.image,
            active_quantity=sku.active_quantity,
            characteristics=[]
        ) for sku in product.skus
    ]
    
    return ProductResponse(
        id=product.id,
        seller_id=product.seller_id,
        category_id=product.category_id,
        title=product.title,
        slug=product.slug or "",
        description=product.description,
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
            CharacteristicValueResponse(
                id=uuid.uuid4(),
                name=char["name"],
                value=char["value"]
            ) for char in (product.characteristics_json or [])
        ],
        skus=skus,
        created_at=product.created_at,
        updated_at=product.updated_at
    )
    

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    # 1. Проверяем, существует ли товар вообще
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # 2. Проверяем ownership (чужой товар → 403)
    if product.seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Product does not belong to you"}
        )
    
    # 3. Если товар уже удалён — возвращаем 204 (идемпотентность)
    if product.deleted:
        return None
    
    # 4. Получаем sku_ids для события в B2C
    skus = db.query(SKU).filter(SKU.product_id == product_id).all()
    sku_ids = [sku.id for sku in skus]
    
    # 5. Мягкое удаление
    product.deleted = True
    db.commit()
    db.refresh(product)
    
    # 6. Отправляем событие DELETED в Moderation
    import uuid as uuid_module
    moderation_idempotency_key = uuid_module.uuid4()
    background_tasks.add_task(
        send_event_to_moderation_sync,
        product_id=product.id,
        seller_id=product.seller_id,
        idempotency_key=moderation_idempotency_key,
        event_type="PRODUCT_DELETED",
        json_before={"deleted": False},
        json_after={"deleted": True},
        category_id=product.category_id
    )
    
    # 7. Отправляем событие PRODUCT_DELETED в B2C
    b2c_idempotency_key = uuid_module.uuid4()
    background_tasks.add_task(
        send_event_to_b2c_sync,
        product_id=product.id,
        sku_ids=sku_ids,
        idempotency_key=b2c_idempotency_key,
        event_type="PRODUCT_DELETED"
    )
    
    return None