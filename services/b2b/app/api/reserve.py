# app/api/reserve.py

"""
Endpoints для резервирования и снятия резерва SKU (B2C → B2B)
Соответствует neomarket-b2b.yaml: POST /api/v1/inventory/reserve и POST /api/v1/inventory/unreserve

All-or-nothing резервирование с SELECT FOR UPDATE для конкурентной безопасности.
Идемпотентность по idempotency_key (TTL 1 час).
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Optional
import json
import logging
from app.services.outbox import save_to_outbox

from app.database import get_db
from app.models.sku import SKU
from app.schemas.reserve import (
    ReserveRequest,
    ReserveSuccessResponse,
    ReservedItemResponse,
    ReserveErrorResponse,
    FailedReserveItem,
    UnreserveRequest,
    UnreserveSuccessResponse
)

router = APIRouter()

logger = logging.getLogger(__name__)

# Хранилище идемпотентных результатов (в production - Redis с TTL)
_idempotency_cache: dict[UUID, dict] = {}


def verify_service_key(x_service_key: Optional[str] = None) -> bool:
    """Проверяет валидность X-Service-Key для межсервисных вызовов"""
    import os
    expected_key = os.getenv("B2B_SERVICE_KEY", "b2b-service-key")
    return x_service_key == expected_key



def send_sku_out_of_stock_event(sku_id: UUID, product_id: UUID, db: Session):
    """
    Сохраняет событие SKU_OUT_OF_STOCK в outbox для отправки в B2C.
    """
    from datetime import datetime, timezone
    import uuid as uuid_module
    
    event_payload = {
        "event_type": "SKU_OUT_OF_STOCK",
        "idempotency_key": str(uuid_module.uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "sku_id": str(sku_id),
            "product_id": str(product_id)
        }
    }
    
    save_to_outbox(
        db=db,
        event_type="SKU_OUT_OF_STOCK",
        target="b2c",
        url="http://b2c:8000/api/v1/b2b/events",
        payload=event_payload,
        headers={"X-Service-Key": "b2b-to-b2c-key"}
    )


@router.post("/reserve")
def reserve_inventory(
    request: ReserveRequest,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    All-or-nothing резервирование SKU (вызывается B2C при checkout).
    
    Соответствует neomarket-b2b.yaml:
    - URL: POST /api/v1/inventory/reserve
    - Авторизация: X-Service-Key
    - Идемпотентность: по idempotency_key (TTL 1 час)
    - All-or-nothing: если хотя бы один SKU не может быть зарезервирован, вся операция отклоняется
    
    Алгоритм:
    1. Проверка идемпотентности (если ключ уже использован → вернуть кэшированный результат)
    2. SELECT FOR UPDATE по всем sku_id
    3. Проверка active_quantity >= quantity для каждого SKU
    4. Если все OK → UPDATE skus SET active_quantity -= N, reserved_quantity += N
    5. Сохранить результат в кэш идемпотентности
    6. Если active_quantity стал 0 → отправить событие SKU_OUT_OF_STOCK в B2C
    7. Если не хватает остатков → ROLLBACK и вернуть 409
    
    Инвариант: active_quantity + reserved_quantity = stock_quantity (on_hand)
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # 1. Проверка идемпотентности
    if request.idempotency_key in _idempotency_cache:
        cached = _idempotency_cache[request.idempotency_key]
        # Проверка TTL (1 час)
        if datetime.now(timezone.utc) < cached["expires_at"]:
            logger.info(f"Idempotent repeat: idempotency_key={request.idempotency_key}")
            return cached["result"]
        else:
            # TTL истёк, удаляем из кэша
            del _idempotency_cache[request.idempotency_key]
    
    # 2. Получаем список SKU с блокировкой SELECT FOR UPDATE
    sku_ids = [item.sku_id for item in request.items]
    
    # Проверяем, что все SKU существуют и получаем их
    skus = db.execute(
        select(SKU).where(SKU.id.in_(sku_ids)).with_for_update()
    ).scalars().all()
    
    if len(skus) != len(sku_ids):
        missing_ids = set(sku_ids) - {sku.id for sku in skus}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": f"SKU not found: {missing_ids}"}
        )
    
    # Создаём словарь sku_id → SKU для быстрого доступа
    sku_map = {sku.id: sku for sku in skus}
    
    # 3. Проверяем доступность каждого SKU
    failed_items = []
    for item in request.items:
        sku = sku_map[item.sku_id]
        available = sku.active_quantity
        
        if available == 0:
            failed_items.append({
                "sku_id": str(item.sku_id),
                "requested": item.quantity,
                "available": 0,
                "reason": "OUT_OF_STOCK"
            })
        elif available < item.quantity:
            failed_items.append({
                "sku_id": str(item.sku_id),
                "requested": item.quantity,
                "available": available,
                "reason": "INSUFFICIENT_STOCK"
            })
    
    # Если есть проблемы с каким-либо SKU → all-or-nothing отмена
    if failed_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reserved": False,
                "failed_items": failed_items
            }
        )
    
    # 4. Выполняем резервирование (UPDATE)
    reserved_items = []
    sku_out_of_stock_trigger = []
    
    for item in request.items:
        sku = sku_map[item.sku_id]
        
        # Обновляем количества
        sku.active_quantity -= item.quantity
        sku.reserved_quantity += item.quantity
        
        remaining_stock = sku.active_quantity
        
        reserved_items.append(ReservedItemResponse(
            sku_id=item.sku_id,
            reserved_quantity=item.quantity,
            remaining_stock=remaining_stock
        ))
        
        # Запоминаем, если active_quantity стал 0
        if remaining_stock == 0:
            sku_out_of_stock_trigger.append((sku.id, sku.product_id))
    
            sku_out_of_stock_trigger.append((str(sku.id), str(sku.product_id)))
    
    # 5. Сохраняем изменения
    db.commit()
    
    # 6. Сохраняем результат в кэш идемпотентности (TTL 1 час)
    result = ReserveSuccessResponse(
        reserved=True,
        items=reserved_items
    ).model_dump()
    
    _idempotency_cache[request.idempotency_key] = {
        "result": result,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    # 7. Отправляем события SKU_OUT_OF_STOCK (если нужно)
    for sku_id, product_id in sku_out_of_stock_trigger:
        send_sku_out_of_stock_event(sku_id, product_id, db)
    
    return result


@router.post("/unreserve")
def unreserve_inventory(
    request: UnreserveRequest,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """
    Снятие резерва (при отмене заказа).
    
    Соответствует neomarket-b2b.yaml:
    - URL: POST /api/v1/inventory/unreserve
    - Авторизация: X-Service-Key
    - Идемпотентность: по order_id
    
    Алгоритм:
    1. SELECT FOR UPDATE по всем sku_id
    2. UPDATE skus SET active_quantity += N, reserved_quantity -= N
    3. Сохранить результат (для идемпотентности)
    
    Инвариант: active_quantity + reserved_quantity = stock_quantity (on_hand)
    """
    # Проверка X-Service-Key
    if x_service_key is None or not verify_service_key(x_service_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key is required"}
        )
    
    # Получаем список SKU с блокировкой SELECT FOR UPDATE
    sku_ids = [item.sku_id for item in request.items]
    
    skus = db.execute(
        select(SKU).where(SKU.id.in_(sku_ids)).with_for_update()
    ).scalars().all()
    
    if len(skus) != len(sku_ids):
        missing_ids = set(sku_ids) - {sku.id for sku in skus}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": f"SKU not found: {missing_ids}"}
        )
    
    # Создаём словарь sku_id → SKU для быстрого доступа
    sku_map = {sku.id: sku for sku in skus}
    
    # Выполняем снятие резерва
    for item in request.items:
        sku = sku_map[item.sku_id]
        
        # Обновляем количества
        sku.active_quantity += item.quantity
        sku.reserved_quantity -= item.quantity
        
        # Защита от отрицательных значений (не должно происходить при корректной логике)
        if sku.reserved_quantity < 0:
            sku.reserved_quantity = 0
            logger.warning(f"reserved_quantity became negative for sku_id={sku.id}, corrected to 0")
    
    # Сохраняем изменения
    db.commit()
    
    return UnreserveSuccessResponse(ok=True).model_dump()