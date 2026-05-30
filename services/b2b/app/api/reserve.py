"""
Endpoints для резервирования и снятия резерва SKU (B2C → B2B)
Соответствует neomarket-b2b.yaml: POST /api/v1/inventory/reserve и POST /api/v1/inventory/unreserve
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Optional
import logging
from app.services.outbox import save_to_outbox

from app.database import get_db
from app.models.sku import SKU
from app.schemas.reserve import (
    ReserveRequest,
    ReserveSuccessResponse,
    ReserveErrorResponse,
    UnreserveRequest,
    UnreserveSuccessResponse,
    InventoryOrderRequest,
    InventoryOrderResponse
)
from app.dependencies.service_keys import verify_b2c_service_key

router = APIRouter()

logger = logging.getLogger(__name__)

_idempotency_cache: dict[UUID, dict] = {}


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


def send_sku_out_of_stock_event(sku_id: UUID, product_id: UUID, db: Session):
    """Сохраняет событие SKU_OUT_OF_STOCK в outbox для отправки в B2C."""
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


@router.post("/reserve", response_model=ReserveSuccessResponse)
def reserve_inventory(
    request: ReserveRequest,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """All-or-nothing резервирование SKU (вызывается B2C при checkout)."""
    
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    # Проверка идемпотентности
    if request.idempotency_key in _idempotency_cache:
        cached = _idempotency_cache[request.idempotency_key]
        if datetime.now(timezone.utc) < cached["expires_at"]:
            logger.info(f"Idempotent repeat: idempotency_key={request.idempotency_key}")
            return cached["result"]
        else:
            del _idempotency_cache[request.idempotency_key]
    
    # SELECT FOR UPDATE
    sku_ids = sorted([item.sku_id for item in request.items])
    skus = db.execute(
        select(SKU).where(SKU.id.in_(sku_ids)).order_by(SKU.id).with_for_update()
    ).scalars().all()
    
    if len(skus) != len(sku_ids):
        missing_ids = set(sku_ids) - {sku.id for sku in skus}
        error_response("INVALID_REQUEST", f"SKU not found: {missing_ids}", 400)
    
    sku_map = {sku.id: sku for sku in skus}
    
    # Проверяем доступность
    failed_items = []
    for item in request.items:
        sku = sku_map[item.sku_id]
        available = sku.active_quantity
        
        if available == 0:
            failed_items.append({"sku_id": str(item.sku_id), "requested": item.quantity, "available": 0, "reason": "OUT_OF_STOCK"})
        elif available < item.quantity:
            failed_items.append({"sku_id": str(item.sku_id), "requested": item.quantity, "available": available, "reason": "INSUFFICIENT_STOCK"})
    
    if failed_items:
        raise HTTPException(409, detail={
            "code": "INSUFFICIENT_STOCK",
            "message": "Some items are out of stock or have insufficient quantity",
            "details": {"failed_items": failed_items}
        })
    
    # Выполняем резервирование
    sku_out_of_stock_trigger = []
    
    for item in request.items:
        sku = sku_map[item.sku_id]
        sku.active_quantity -= item.quantity
        sku.reserved_quantity += item.quantity
        remaining_stock = sku.active_quantity
        
        if remaining_stock == 0:
            sku_out_of_stock_trigger.append((sku.id, sku.product_id))
    
    db.commit()
    
    result = ReserveSuccessResponse(
        order_id=request.order_id,
        status="RESERVED",
        reserved_at=datetime.now(timezone.utc)
    )
    
    _idempotency_cache[request.idempotency_key] = {
        "result": result,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    for sku_id, product_id in sku_out_of_stock_trigger:
        send_sku_out_of_stock_event(sku_id, product_id, db)
    
    return result


@router.post("/fulfill", response_model=InventoryOrderResponse)
def fulfill_inventory(
    request: InventoryOrderRequest,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """Списание резерва при доставке (вызывается B2C admin). Идемпотентно по order_id."""
    
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    from app.models.fulfill_operation import FulfillOperation
    
    existing = db.query(FulfillOperation).filter(
        FulfillOperation.order_id == request.order_id
    ).first()
    
    if existing:
        logger.info(f"Idempotent fulfill repeat: order_id={request.order_id}")
        return InventoryOrderResponse(
            order_id=request.order_id,
            status="FULFILLED",
            processed_at=existing.processed_at
        )
    
    sku_ids = sorted([item.sku_id for item in request.items])
    skus = db.execute(
        select(SKU).where(SKU.id.in_(sku_ids)).order_by(SKU.id).with_for_update()
    ).scalars().all()
    
    if len(skus) != len(sku_ids):
        missing_ids = set(sku_ids) - {sku.id for sku in skus}
        error_response("INVALID_REQUEST", f"SKU not found: {missing_ids}", 400)
    
    sku_map = {sku.id: sku for sku in skus}
    
    for item in request.items:
        sku = sku_map[item.sku_id]
        if item.quantity > sku.reserved_quantity:
            raise HTTPException(409, detail={
                "code": "INSUFFICIENT_RESERVED",
                "message": f"Cannot fulfill {item.quantity}, only {sku.reserved_quantity} is reserved",
                "details": {"sku_id": str(sku.id), "requested": item.quantity, "available": sku.reserved_quantity}
            })
    
    for item in request.items:
        sku = sku_map[item.sku_id]
        sku.reserved_quantity -= item.quantity
        sku.stock_quantity -= item.quantity
        
        if sku.reserved_quantity < 0:
            sku.reserved_quantity = 0
            logger.warning(f"reserved_quantity became negative for sku_id={sku.id}, corrected to 0")
    
        if sku.stock_quantity < 0:
            sku.stock_quantity = 0
            logger.warning(f"stock_quantity became negative for sku_id={sku.id}, corrected to 0")
        
        sku.active_quantity = sku.stock_quantity - sku.reserved_quantity
        if sku.active_quantity < 0:
            sku.active_quantity = 0
    
    fulfill_op = FulfillOperation(
        order_id=request.order_id,
        processed_at=datetime.now(timezone.utc)
    )
    db.add(fulfill_op)
    db.commit()
    
    return InventoryOrderResponse(
        order_id=request.order_id,
        status="FULFILLED",
        processed_at=datetime.now(timezone.utc)
    )


@router.post("/unreserve", response_model=UnreserveSuccessResponse)
def unreserve_inventory(
    request: UnreserveRequest,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    db: Session = Depends(get_db)
):
    """Снятие резерва (при отмене заказа). Идемпотентно по order_id."""
    
    if x_service_key is None or not verify_b2c_service_key(x_service_key):
        error_response("UNAUTHORIZED", "X-Service-Key is required", 401)
    
    from app.models.unreserve_operation import UnreserveOperation
        
    existing = db.query(UnreserveOperation).filter(
        UnreserveOperation.order_id == request.order_id
    ).first()
        
    if existing:
        logger.info(f"Idempotent unreserve repeat: order_id={request.order_id}")
        return UnreserveSuccessResponse(
            order_id=request.order_id,
            status="UNRESERVED",
            processed_at=existing.processed_at
        )
    
    sku_ids = sorted([item.sku_id for item in request.items])
    skus = db.execute(
        select(SKU).where(SKU.id.in_(sku_ids)).order_by(SKU.id).with_for_update()
    ).scalars().all()
    
    if len(skus) != len(sku_ids):
        missing_ids = set(sku_ids) - {sku.id for sku in skus}
        error_response("INVALID_REQUEST", f"SKU not found: {missing_ids}", 400)
    
    sku_map = {sku.id: sku for sku in skus}
    
    for item in request.items:
        sku = sku_map[item.sku_id]
        reserved_before = sku.reserved_quantity
        
        if item.quantity > reserved_before:
            raise HTTPException(409, detail={
                "code": "INSUFFICIENT_RESERVED",
                "message": f"Cannot unreserve {item.quantity}, only {reserved_before} is reserved",
                "details": {"sku_id": str(sku.id), "requested": item.quantity, "available": reserved_before}
            })
        
        real_qty = min(item.quantity, reserved_before)
        sku.active_quantity += real_qty
        sku.reserved_quantity -= real_qty
    
    unreserve_op = UnreserveOperation(
        order_id=request.order_id,
        processed_at=datetime.now(timezone.utc)
    )
    db.add(unreserve_op)
    db.commit()
    
    return UnreserveSuccessResponse(
        order_id=request.order_id,
        status="UNRESERVED",
        processed_at=datetime.now(timezone.utc)
    )