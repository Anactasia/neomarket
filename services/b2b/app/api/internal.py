from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import os
import uuid as uuid_module
import logging

from app.database import get_db
from app.models.product import Product
from app.models.sku import SKU
from app.schemas.moderation import ModerationEventRequest, ModerationEventType
from app.services.outbox import save_to_outbox
from app.dependencies.service_keys import verify_moderation_service_key

router = APIRouter()
logger = logging.getLogger(__name__)


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


# TODO: заменить на БД в production
_moderation_idempotency_cache: dict[str, bool] = {}


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
def receive_moderation_event(
    event: ModerationEventRequest,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/moderation/events - приём событий от Moderation Service.
    
    Соответствует спецификации neomarket-b2b.yaml.
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_moderation_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    # Проверка идемпотентности
    cache_key = f"moderation:{event.idempotency_key}"
    if cache_key in _moderation_idempotency_cache:
        logger.info(f"Duplicate moderation event: {event.idempotency_key}")
        return None
    
    # Поиск товара
    product = db.query(Product).filter(Product.id == event.product_id).first()
    if not product:
        error_response("NOT_FOUND", "Product not found", 404)
    
    logger.info(f"Processing moderation event for product {product.id}: {event.event_type}")
    
    # Обработка MODERATED
    if event.event_type == ModerationEventType.MODERATED:
        product.status = "MODERATED"
        product.blocked = False
        product.blocking_reason_id = None
        product.moderation_comment = event.moderator_comment
        product.field_reports_json = []
        product.published_at = datetime.now(timezone.utc)
    
    # Обработка BLOCKED
    elif event.event_type == ModerationEventType.BLOCKED:
        if event.hard_block:
            product.status = "HARD_BLOCKED"
        else:
            product.status = "BLOCKED"
        product.blocked = True
        product.blocking_reason_id = event.blocking_reason_id
        product.moderation_comment = event.moderator_comment
        
        if event.field_reports:
            product.field_reports_json = [
                {
                    "field_name": fr.field_name,
                    "sku_id": str(fr.sku_id) if fr.sku_id else None,
                    "comment": fr.comment
                }
                for fr in event.field_reports
            ]
        
        # Отправка события в B2C при наличии остатков
        skus_with_stock = db.query(SKU).filter(
            SKU.product_id == product.id,
            SKU.active_quantity > 0
        ).all()
        
        if skus_with_stock:
            b2c_idempotency_key = uuid_module.uuid4()
            
            event_payload = {
                "event_type": "PRODUCT_BLOCKED" if not event.hard_block else "PRODUCT_HARD_BLOCKED",
                "idempotency_key": str(b2c_idempotency_key),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "product_id": str(product.id),
                    "sku_ids": [str(sku.id) for sku in skus_with_stock]
                }
            }
            
            save_to_outbox(
                db=db,
                event_type=event_payload["event_type"],
                target="b2c",
                url="http://b2c:8000/api/v1/b2b/events",
                payload=event_payload,
                headers={"X-Service-Key": os.getenv("B2B_TO_B2C_KEY", "b2b-to-b2c-key")}
            )
            
            logger.info(f"Sent B2C event for product {product.id}: {event_payload['event_type']}")
    
    db.commit()
    _moderation_idempotency_cache[cache_key] = True
    
    return None



# @router.post("/moderation-callback")
# def moderation_callback(
#     callback: dict,
#     db: Session = Depends(get_db)
# ):
#     """
#     Получить результат модерации от Moderation сервиса (legacy).
#     """
#     product_id = callback.get("product_id")
#     decision = callback.get("decision")  # APPROVED or DECLINED
#     comment = callback.get("comment")
    
#     product = db.query(Product).filter(Product.id == product_id).first()
#     if not product:
#         raise HTTPException(status_code=404, detail="Product not found")
    
#     if decision == "APPROVED":
#         product.status = "MODERATED"
#         product.published_at = datetime.utcnow()
#     else:
#         product.status = "BLOCKED"
#         product.moderation_comment = comment
    
#     db.commit()
    
#     return {
#         "success": True,
#         "product_id": product_id,
#         "new_status": product.status
#     }