# app/api/skus.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import uuid as uuid_module
from app.services.outbox import save_to_outbox

from app.database import get_db
from app.models.sku import SKU, SKUCharacteristic
from app.models.product import Product

from app.schemas.sku import (
    SKUCreate,
    SKUCreateWithValidation,
    SKU as SKUSchema,
    SKUUpdate,
    SKUUpdateWithValidation,
    SKUImageResponse,
    SKUCharacteristicResponse,
    SKUImageCreate  # ← добавить импорт
)
from app.schemas.common import CharacteristicValueResponse, CharacteristicValue
from app.schemas.product import ProductStatus
from app.dependencies.auth import get_current_seller
from app.models.seller import Seller

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
    db: Session,  # ← ДОБАВЛЯЕМ db
    moderation_url: str = "http://moderation:8000",
    event_type: str = "PRODUCT_CREATED",
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
        target="moderation",
        url=f"{moderation_url}/api/v1/b2b/events",
        payload=event_payload,
        headers={"X-Service-Key": "b2b-service-key"}
    )
    

@router.post("/", response_model=SKUSchema, status_code=status.HTTP_201_CREATED)
def create_sku(
    sku: SKUCreateWithValidation,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Создать новый SKU (вариант товара).
    """
    # 1. Проверяем существование товара
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    # 2. Проверяем, что товар принадлежит текущему продавцу (IDOR защита)
    if product.seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "Product does not belong to the authenticated seller"}
        )
    
    # 3. Проверяем, что товар не в статусе HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED.value:
        error_response("FORBIDDEN", "Cannot add SKU to hard-blocked product", 403)
    
    
    
    # 4. Создаём SKU (используем URL первого изображения для поля image)
    first_image = sku.images[0] if sku.images else None
    db_sku = SKU(
        product_id=sku.product_id,
        name=sku.name,
        price=sku.price,
        cost_price=sku.cost_price,
        discount=sku.discount,
        image=first_image.url if first_image else None,  
        stock_quantity=0,
        active_quantity=0,
        reserved_quantity=0,
        article=None
    )
    db.add(db_sku)
    db.flush()
    
    # 5. Сохраняем характеристики SKU
    for char in sku.characteristics:
        db_char = SKUCharacteristic(
            sku_id=db_sku.id,
            value_string=char.value
        )
        db.add(db_char)
    
    # 6. Проверяем, первый ли это SKU для товара и нужно ли re-moderation
    sku_count = db.query(SKU).filter(SKU.product_id == sku.product_id).count()
    is_first_sku = sku_count == 1 and product.status == ProductStatus.CREATED.value
    needs_re_moderation = product.status in [ProductStatus.MODERATED.value, ProductStatus.BLOCKED.value]
    
    # 7. Меняем статус товара при необходимости
    if is_first_sku or needs_re_moderation:
        product.status = ProductStatus.ON_MODERATION.value
        db.flush()
    
    db.commit()
    db.refresh(db_sku)
    
    # 8. Отправляем событие в Moderation
    if is_first_sku:
        idempotency_key = uuid_module.uuid4()
        json_after = {
            "product_id": str(sku.product_id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": product.status
        }
        send_event_to_moderation_sync(  
            product_id=sku.product_id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            db=db,  # ← добавили db
            event_type="PRODUCT_CREATED",
            json_after=json_after,
            category_id=product.category_id
        )
    elif needs_re_moderation:
        idempotency_key = uuid_module.uuid4()
        json_before = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": ProductStatus.MODERATED.value if product.status == ProductStatus.MODERATED.value else ProductStatus.BLOCKED.value
        }
        json_after = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": ProductStatus.ON_MODERATION.value
        }
        send_event_to_moderation_sync( 
            product_id=sku.product_id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            db=db,  # ← добавили db
            event_type="PRODUCT_EDITED",
            json_before=json_before,
            json_after=json_after,
            category_id=product.category_id
        )
    # 9. Формируем ответ (без изменений)
    return SKUSchema(
        id=db_sku.id,
        product_id=db_sku.product_id,
        name=db_sku.name,
        price=db_sku.price,
        cost_price=db_sku.cost_price,
        discount=db_sku.discount,
        stock_quantity=db_sku.stock_quantity,
        active_quantity=db_sku.active_quantity,
        reserved_quantity=db_sku.reserved_quantity,
        article=db_sku.article,
        images=[
            SKUImageResponse(
                id=uuid_module.uuid4(),
                url=img.url,
                ordering=img.ordering or 0
            ) for img in sku.images
        ],
        characteristics=[
            SKUCharacteristicResponse(
                id=uuid_module.uuid4(),
                name=char.name,
                value=char.value
            ) for char in sku.characteristics
        ],
        created_at=db_sku.created_at,
        updated_at=db_sku.updated_at
    )


@router.patch("/{sku_id}", response_model=SKUSchema, status_code=status.HTTP_200_OK)
def update_sku(
    sku_id: UUID,
    sku_update: SKUUpdateWithValidation,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Обновить SKU (вариант товара).
    
    Побочные эффекты:
    - Если товар в статусе MODERATED или BLOCKED → товар переходит в ON_MODERATION
    - Отправляется событие EDITED в Moderation Service
    - reserved_quantity сохраняется (не сбрасывается)
    """
    # 1. Проверяем существование SKU
    db_sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not db_sku:
        error_response("NOT_FOUND", "SKU not found", 404)
    
    # 2. Проверяем родительский товар
    product = db.query(Product).filter(Product.id == db_sku.product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    # 3. Проверяем, что товар не в статусе HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED.value:
        error_response("FORBIDDEN", "Cannot edit hard-blocked product", 403)
    
    # 4. Проверяем, что товар принадлежит текущему продавцу (IDOR защита)
    if product.seller_id != current_seller.id:
        # ИСПРАВЛЕНО: NOT_OWNER → FORBIDDEN
        error_response("NOT_OWNER", "SKU does not belong to the authenticated seller", 403)
    
    # 5. Сохраняем старые данные для события
    old_product_status = product.status
    
    # 6. Сохраняем reserved_quantity перед обновлением
    old_reserved_quantity = db_sku.reserved_quantity
    
    # 7. Обновляем поля SKU
    for field, value in sku_update.model_dump(exclude_unset=True).items():
        if field == 'characteristics' and value is not None:
            # Обновляем характеристики
            db.query(SKUCharacteristic).filter(SKUCharacteristic.sku_id == db_sku.id).delete()
            for char in value:
                db_char = SKUCharacteristic(
                    sku_id=db_sku.id,
                    value_string=char.value
                )
                db.add(db_char)
        elif field == 'images' and value is not None:
            # Обновляем основное изображение (берем первое)
            if len(value) > 0:
                db_sku.image = value[0].url
        elif value is not None:
            setattr(db_sku, field, value)
    
    # 8. Восстанавливаем reserved_quantity (сохраняем активные резервы)
    db_sku.reserved_quantity = old_reserved_quantity
    
    # 9. ИСПРАВЛЕНО: проверяем, нужно ли менять статус товара
    # Статус меняется, если товар был в MODERATED или BLOCKED
    needs_status_change = product.status in [ProductStatus.MODERATED.value, ProductStatus.BLOCKED.value]
    
    # 10. Если товар в MODERATED или BLOCKED → меняем статус на ON_MODERATION
    if needs_status_change:
        product.status = ProductStatus.ON_MODERATION.value
    
    db.commit()
    db.refresh(db_sku)
    db.refresh(product)
    
    # 11. ИСПРАВЛЕНО: отправляем событие EDITED в Moderation
    # Событие отправляется, если статус изменился или товар уже был на модерации
    if needs_status_change or old_product_status != ProductStatus.CREATED.value:
        idempotency_key = uuid_module.uuid4()
        
        # ИСПРАВЛЕНО: правильно формируем json_before
        json_before = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": old_product_status  # старый статус
        }
        
        json_after = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": product.status  # новый статус
        }
        
        send_event_to_moderation_sync(
            product_id=product.id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            db=db,  # ← добавить
            event_type="PRODUCT_EDITED",
            json_before=json_before,
            json_after=json_after,
            category_id=product.category_id
        )
    
    # 12. Формируем ответ
    return SKUSchema(
        id=db_sku.id,
        product_id=db_sku.product_id,
        name=db_sku.name,
        price=db_sku.price,
        cost_price=db_sku.cost_price,
        discount=db_sku.discount,
        stock_quantity=db_sku.stock_quantity,
        active_quantity=db_sku.active_quantity,
        reserved_quantity=db_sku.reserved_quantity,
        article=db_sku.article,
        images=[
            SKUImageResponse(
                id=uuid_module.uuid4(),
                url=db_sku.image or "",
                ordering=0
            )
        ] if db_sku.image else [],
        characteristics=[
            SKUCharacteristicResponse(
                id=char.id,
                name="Characteristic",
                value=char.value_string or ""
            ) for char in db_sku.characteristics
        ],
        created_at=db_sku.created_at,
        updated_at=db_sku.updated_at
    )


@router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sku(
    sku_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "SKU not found"})
    
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if not product:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    

    if product.status == ProductStatus.HARD_BLOCKED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Cannot delete SKU of hard-blocked product"}
        )
    
    if product.seller_id != current_seller.id:
        raise HTTPException(403, detail={"code": "NOT_OWNER", "message": "SKU does not belong to you"})
    
    # проверка активных резервов
    if sku.reserved_quantity > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONFLICT", "message": "Cannot delete SKU with active reserves"}
        )

    sku_count = db.query(SKU).filter(SKU.product_id == product.id).count()
    if sku_count == 1 and product.status == ProductStatus.ON_MODERATION.value:
        product.status = ProductStatus.CREATED.value
    
    db.delete(sku)
    db.commit()
    return None


@router.put("/{sku_id}/quantity", response_model=SKUSchema)
def update_sku_quantity(
    sku_id: UUID,
    quantity: int,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Обновить остаток SKU вручную (только свой SKU)"""
    # Проверяем существование SKU
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "SKU not found"}
        )
    
    # Проверяем родительский товар
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # Проверяем, что товар принадлежит текущему продавцу
    if product.seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_OWNER", "message": "SKU does not belong to you"}
        )
    
    sku.stock_quantity = quantity
    db.commit()
    db.refresh(sku)
    
    # Формируем ответ
    return SKUSchema(
        id=sku.id,
        product_id=sku.product_id,
        name=sku.name,
        price=sku.price,
        cost_price=sku.cost_price,
        discount=sku.discount,
        stock_quantity=sku.stock_quantity,
        active_quantity=sku.active_quantity,
        reserved_quantity=sku.reserved_quantity,
        article=sku.article,
        images=[
            SKUImageResponse(
                id=uuid_module.uuid4(),
                url=sku.image or "",
                ordering=0
            )
        ] if sku.image else [],
        characteristics=[],
        created_at=sku.created_at,
        updated_at=sku.updated_at
    )