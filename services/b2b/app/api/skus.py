from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from uuid import UUID
import uuid as uuid_module
import os
from app.services.outbox import save_to_outbox

from app.database import get_db
from app.models.sku import SKU, SKUCharacteristic, SKUImage
from app.models.product import Product

from app.schemas.sku import (
    SKUCreate,
    SKU as SKUSchema,
    SKUUpdate,
    SKUImageResponse,
    SKUImageCreate
)
from app.schemas.common import CharacteristicValueResponse, CharacteristicValue
from app.schemas.product import ProductStatus, ImageAttachRequest, ImageUpdateRequest
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
    db: Session,
    moderation_url: str = "http://moderation:8000",
    event_type: str = "PRODUCT_CREATED",
    json_before: Optional[dict] = None,
    json_after: Optional[dict] = None,
    category_id: Optional[UUID] = None
):
    """Сохраняет событие в outbox вместо прямой отправки."""
    from datetime import datetime, timezone
    
    payload: dict = {
        "product_id": str(product_id),
        "seller_id": str(seller_id),
    }
    if category_id:
        payload["category_id"] = str(category_id)
    
    if event_type == "PRODUCT_CREATED":
        payload["json_after"] = json_after or {}
    elif event_type == "PRODUCT_EDITED" or event_type == "SKU_EDITED":
        payload["json_before"] = json_before or {}
        payload["json_after"] = json_after or {}
    
    event_payload = {
        "event_type": event_type,
        "idempotency_key": str(idempotency_key),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }
    
    save_to_outbox(
        db=db,
        event_type=event_type,
        target="moderation",
        url=f"{moderation_url}/api/v1/b2b/events",
        payload=event_payload,
        headers={"X-Service-Key": os.getenv("B2B_TO_MOD_KEY", "")}
    )


def _sku_to_schema(sku: SKU) -> SKUSchema:
    """Преобразовать модель SKU в схему ответа"""
    return SKUSchema(
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
            CharacteristicValueResponse(
                id=char.id,
                name=char.characteristic.name if char.characteristic else "Characteristic",
                value=char.value_string or ""
            ) for char in sku.characteristics
        ],
        created_at=sku.created_at,
        updated_at=sku.updated_at or sku.created_at
    )


# ========== ОСНОВНЫЕ ЭНДПОИНТЫ (по спецификации) ==========

@router.get("/{sku_id}", response_model=SKUSchema)
def get_sku(
    sku_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Получить SKU (seller view)"""
    sku = db.query(SKU).options(
        selectinload(SKU.images),
        selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic)
    ).filter(SKU.id == sku_id).first()
    
    if not sku:
        error_response("NOT_FOUND", "SKU not found", 404)
    
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "SKU does not belong to you", 403)
    
    return _sku_to_schema(sku)


@router.post("/", response_model=SKUSchema, status_code=status.HTTP_201_CREATED)
def create_sku(
    sku: SKUCreate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Создать новый SKU (вариант товара)."""
    # 1. Проверяем существование товара
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    # 2. Проверяем, что товар принадлежит текущему продавцу
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Product does not belong to the authenticated seller", 403)
    
    # 3. Проверяем, что товар не в статусе HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED:
        error_response("FORBIDDEN", "Cannot add SKU to hard-blocked product", 403)
    
    # 4. Создаём SKU
    db_sku = SKU(
        product_id=sku.product_id,
        name=sku.name,
        price=sku.price,
        cost_price=sku.cost_price,
        discount=sku.discount,
        stock_quantity=0,
        active_quantity=0,
        reserved_quantity=0,
        article=sku.article
    )
    db.add(db_sku)
    db.flush()
    
    # 5. Сохраняем изображения SKU
    for idx, img in enumerate(sku.images):
        db_image = SKUImage(
            sku_id=db_sku.id,
            url=img.url,
            sort_order=img.ordering or idx
        )
        db.add(db_image)
    
    # 6. Сохраняем характеристики SKU
    for char in sku.characteristics:
        db_char = SKUCharacteristic(
            sku_id=db_sku.id,
            characteristic_id=None,  # будет заполняться при создании характеристики
            value_string=str(char.value) if isinstance(char.value, (str, int, float, bool)) else char.value,
            value_int=int(char.value) if isinstance(char.value, int) else None,
            value_float=float(char.value) if isinstance(char.value, float) else None,
            value_bool=bool(char.value) if isinstance(char.value, bool) else None
        )
        db.add(db_char)
    
    # 7. Проверяем, первый ли это SKU
    sku_count = db.query(SKU).filter(SKU.product_id == sku.product_id).count()
    is_first_sku = sku_count == 1 and product.status == ProductStatus.CREATED
    needs_re_moderation = product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]
    
    if is_first_sku or needs_re_moderation:
        product.status = ProductStatus.ON_MODERATION
        db.flush()
    
    db.commit()
    db.refresh(db_sku)
    
    # 8. Отправляем событие в Moderation
    if is_first_sku:
        key_string = f"{sku.product_id}:PRODUCT_CREATED"
        idempotency_key = str(uuid_module.uuid5(uuid_module.NAMESPACE_DNS, key_string))
        
        json_after = {
            "product_id": str(sku.product_id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": product.status.value if hasattr(product.status, 'value') else str(product.status)
        }
        send_event_to_moderation_sync(
            product_id=sku.product_id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            db=db,
            event_type="PRODUCT_CREATED",
            json_after=json_after,
            category_id=product.category_id
        )
    elif needs_re_moderation:
        old_status = product.status
        key_string = f"{product.id}:SKU_EDITED:{old_status}:{product.status}"
        idempotency_key = str(uuid_module.uuid5(uuid_module.NAMESPACE_DNS, key_string))
        
        json_before = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": old_status.value if hasattr(old_status, 'value') else str(old_status)
        }
        json_after = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": product.status.value if hasattr(product.status, 'value') else str(product.status)
        }
        send_event_to_moderation_sync(
            product_id=sku.product_id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            db=db,
            event_type="SKU_EDITED",
            json_before=json_before,
            json_after=json_after,
            category_id=product.category_id
        )
    
    db.refresh(db_sku)
    return _sku_to_schema(db_sku)


@router.patch("/{sku_id}", response_model=SKUSchema, status_code=status.HTTP_200_OK)
def update_sku(
    sku_id: UUID,
    sku_update: SKUUpdate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Обновить SKU (вариант товара)."""
    
    # 1. Проверяем существование SKU с загрузкой связанных данных
    db_sku = db.query(SKU).options(
        selectinload(SKU.images),
        selectinload(SKU.characteristics).selectinload(SKUCharacteristic.characteristic)
    ).filter(SKU.id == sku_id).first()
    
    if not db_sku:
        error_response("NOT_FOUND", "SKU not found", 404)
    
    # 2. Проверяем родительский товар
    product = db.query(Product).filter(Product.id == db_sku.product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    # 3. Проверяем, что товар не в статусе HARD_BLOCKED
    if product.status == ProductStatus.HARD_BLOCKED:
        error_response("FORBIDDEN", "Cannot edit hard-blocked product", 403)
    
    # 4. Проверяем, что товар принадлежит текущему продавцу
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "SKU does not belong to the authenticated seller", 403)
    
    # 5. Сохраняем старые данные
    old_product_status = product.status
    
    # 6. Обновляем поля SKU
    update_data = sku_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'characteristics' and value is not None:
            db.query(SKUCharacteristic).filter(SKUCharacteristic.sku_id == db_sku.id).delete()
            for char in value:
                db_char = SKUCharacteristic(
                    sku_id=db_sku.id,
                    characteristic_id=None,
                    value_string=str(char.value) if isinstance(char.value, (str, int, float, bool)) else char.value,
                    value_int=int(char.value) if isinstance(char.value, int) else None,
                    value_float=float(char.value) if isinstance(char.value, float) else None,
                    value_bool=bool(char.value) if isinstance(char.value, bool) else None
                )
                db.add(db_char)
        elif field == 'images' and value is not None:
            db.query(SKUImage).filter(SKUImage.sku_id == db_sku.id).delete()
            for idx, img in enumerate(value):
                db_image = SKUImage(
                    sku_id=db_sku.id,
                    url=img.url,
                    sort_order=img.ordering or idx
                )
                db.add(db_image)
        elif value is not None:
            setattr(db_sku, field, value)
    
    # 7. Меняем статус товара если нужно
    needs_status_change = product.status in [ProductStatus.MODERATED, ProductStatus.BLOCKED]
    
    if needs_status_change:
        product.status = ProductStatus.ON_MODERATION
    
    db.commit()
    db.refresh(db_sku)
    db.refresh(product)
    
    # 8. Отправляем событие
    if needs_status_change or old_product_status != ProductStatus.CREATED:
        idempotency_key = uuid_module.uuid4()
        
        json_before = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": old_product_status.value if hasattr(old_product_status, 'value') else str(old_product_status)
        }
        
        json_after = {
            "product_id": str(product.id),
            "seller_id": str(product.seller_id),
            "title": product.title,
            "status": product.status.value if hasattr(product.status, 'value') else str(product.status)
        }
        
        send_event_to_moderation_sync(
            product_id=product.id,
            seller_id=product.seller_id,
            idempotency_key=idempotency_key,
            db=db,
            event_type="SKU_EDITED",
            json_before=json_before,
            json_after=json_after,
            category_id=product.category_id
        )
    
    db.refresh(db_sku)
    return _sku_to_schema(db_sku)


@router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sku(
    sku_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Удалить SKU. Запрещено, если reserved_quantity > 0."""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        error_response("NOT_FOUND", "SKU not found", 404)
    
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    if product.status == ProductStatus.HARD_BLOCKED:
        error_response("FORBIDDEN", "Cannot delete SKU of hard-blocked product", 403)
    
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "SKU does not belong to you", 403)
    
    if sku.reserved_quantity > 0:
        error_response("CONFLICT", "Cannot delete SKU with active reserves", 409)
    
    sku_count = db.query(SKU).filter(SKU.product_id == product.id).count()
    if sku_count == 1 and product.status == ProductStatus.ON_MODERATION:
        product.status = ProductStatus.CREATED
    
    db.delete(sku)
    db.commit()
    return None


@router.post("/{sku_id}/images", response_model=SKUImageResponse, status_code=status.HTTP_201_CREATED)
def add_sku_image(
    sku_id: UUID,
    image_data: ImageAttachRequest,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Прикрепить изображение к SKU"""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        error_response("NOT_FOUND", "SKU not found", 404)
    
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "SKU does not belong to you", 403)
    
    db_image = SKUImage(
        sku_id=sku_id,
        url=image_data.url or "",
        sort_order=image_data.ordering
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    return SKUImageResponse(
        id=db_image.id,
        url=db_image.url,
        ordering=db_image.sort_order
    )


@router.patch("/images/{image_id}", response_model=SKUImageResponse)
def update_sku_image(
    image_id: UUID,
    image_data: ImageUpdateRequest,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Обновить изображение SKU"""
    db_image = db.query(SKUImage).filter(SKUImage.id == image_id).first()
    if not db_image:
        error_response("NOT_FOUND", "Image not found", 404)
    
    sku = db.query(SKU).filter(SKU.id == db_image.sku_id).first()
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Image does not belong to you", 403)
    
    if image_data.url is not None:
        db_image.url = image_data.url
    if image_data.ordering is not None:
        db_image.sort_order = image_data.ordering
    
    db.commit()
    db.refresh(db_image)
    
    return SKUImageResponse(
        id=db_image.id,
        url=db_image.url,
        ordering=db_image.sort_order
    )


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sku_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Удалить изображение SKU"""
    db_image = db.query(SKUImage).filter(SKUImage.id == image_id).first()
    if not db_image:
        error_response("NOT_FOUND", "Image not found", 404)
    
    sku = db.query(SKU).filter(SKU.id == db_image.sku_id).first()
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if product.seller_id != current_seller.id:
        error_response("NOT_OWNER", "Image does not belong to you", 403)
    
    db.delete(db_image)
    db.commit()
    return None