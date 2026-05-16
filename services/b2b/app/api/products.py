from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
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


def error_response(code: str, message: str, status_code: int = 422):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
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
    except Exception:
        # fire-and-forget: не блокируем ответ при недоступности Moderation
        pass
    

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


@router.patch("/{product_id}", response_model=ProductResponse, status_code=status.HTTP_200_OK)
def update_product(
    product_id: UUID,
    product_update: ProductUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Обновить товар (только свои товары).
    
    Побочные эффекты:
    - Если товар в статусе MODERATED или BLOCKED → товар переходит в ON_MODERATION
    - Отправляется событие EDITED в Moderation Service (всегда при редактировании)
    """
    # 1. Проверяем существование товара
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.seller_id == current_seller.id
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # 2. Проверяем, что товар не в статусе HARD_BLOCKED
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
    
    # Формируем ответ (по спецификации neomarket-b2b.yaml)
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
        skus=[],
        created_at=product.created_at,
        updated_at=product.updated_at
    )


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