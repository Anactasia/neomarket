# app/api/skus.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import uuid as uuid_module

from app.database import get_db
from app.models.sku import SKU, SKUCharacteristic
from app.models.product import Product

from app.schemas.sku import (
    SKUCreate,
    SKUCreateWithValidation,
    SKU as SKUSchema,
    SKUImageResponse,
    SKUCharacteristicResponse
)
from app.schemas.common import CharacteristicValueResponse, CharacteristicValue
from app.schemas.product import ProductStatus
from app.dependencies.auth import get_current_seller
from app.models.seller import Seller

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


def send_event_to_moderation_sync(
    product_id: UUID,
    seller_id: UUID,
    idempotency_key: str,
    moderation_url: str = "http://moderation:8000"
):
    """
    Отправляет событие CREATED в Moderation Service синхронно.
    Для production рекомендуется outbox pattern или асинхронная очередь.
    """
    import httpx
    from datetime import datetime, timezone
    
    event_payload = {
        "idempotency_key": str(idempotency_key),
        "product_id": str(product_id),
        "seller_id": str(seller_id),
        "event": "CREATED",
        "date": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{moderation_url}/api/v1/events/product",
                json=event_payload,
                headers={"X-Service-Key": "b2b-service-key"}
            )
    except Exception:
        # fire-and-forget: не блокируем ответ при недоступности Moderation
        pass


@router.post("/", response_model=SKUSchema, status_code=status.HTTP_201_CREATED)
def create_sku(
    sku: SKUCreateWithValidation,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Создать новый SKU (вариант товара).
    
    Побочные эффекты:
    - Если это первый SKU для товара со статусом CREATED → товар переходит в ON_MODERATION
    - Отправляется событие CREATED в Moderation Service (через background task)
    """
    # 1. Проверяем существование товара
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    # 2. Проверяем, что товар не в статусе HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED.value:
        error_response("FORBIDDEN", "Cannot add SKU to hard-blocked product", 403)
    
    # 3. Проверяем, что товар принадлежит текущему продавцу
    if product.seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Product does not belong to you"}
        )
    
    # 4. Проверяем наличие image в запросе
    if not sku.image:
        error_response("INVALID_REQUEST", "image is required", 400)
    
    # 5. Создаём SKU
    db_sku = SKU(
        product_id=sku.product_id,
        name=sku.name,
        price=sku.price,
        cost_price=sku.cost_price,
        discount=sku.discount,
        image=sku.image,
        stock_quantity=0,
        active_quantity=0,
        reserved_quantity=0,
        article=None
    )
    db.add(db_sku)
    db.flush()
    
    # 6. Сохраняем характеристики SKU
    for char in sku.characteristics:
        db_char = SKUCharacteristic(
            sku_id=db_sku.id,
            value_string=char.value
        )
        db.add(db_char)
    
    # 7. Проверяем, первый ли это SKU для товара
    sku_count = db.query(SKU).filter(SKU.product_id == sku.product_id).count()
    is_first_sku = sku_count == 1 and product.status == ProductStatus.CREATED.value
    
    # 8. Если первый SKU и товар в CREATED → меняем статус на ON_MODERATION
    if is_first_sku:
        product.status = ProductStatus.ON_MODERATION.value
        db.flush()
    
    db.commit()
    db.refresh(db_sku)
    
    # 9. Отправляем событие в Moderation (background task)
    if is_first_sku:
        idempotency_key = uuid_module.uuid4()
        background_tasks.add_task(
            send_event_to_moderation_sync,
            product_id=sku.product_id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key
        )
    
    # 10. Формируем ответ
    return SKUSchema(
        id=db_sku.id,
        product_id=db_sku.product_id,
        name=db_sku.name,
        price=db_sku.price,
        cost_price=db_sku.cost_price,
        discount=db_sku.discount,
        image=db_sku.image,
        stock_quantity=db_sku.stock_quantity,
        active_quantity=db_sku.active_quantity,
        reserved_quantity=db_sku.reserved_quantity,
        article=db_sku.article,
        images=[],
        characteristics=[],
        created_at=db_sku.created_at,
        updated_at=db_sku.updated_at
    )

@router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sku(sku_id: UUID, db: Session = Depends(get_db)):
    """Удалить SKU"""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SKU не найден"
        )
    
    db.delete(sku)
    db.commit()
    return None





@router.put("/{sku_id}/quantity", response_model=SKUSchema)
def update_sku_quantity(
    sku_id: UUID,
    quantity: int,
    db: Session = Depends(get_db)
):
    """Обновить остаток SKU вручную"""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(status_code=404, detail="SKU не найден")
    
    sku.quantity = quantity
    db.commit()
    db.refresh(sku)
    return sku