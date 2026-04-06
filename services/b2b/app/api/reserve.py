# app/api/reserve.py (создать)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from uuid import uuid4

from app.database import get_db
from app.models.sku import SKU
from app.models.reservation import SKUReservation  # нужно создать модель

router = APIRouter()

@router.post("/")
def reserve_items(request: dict, db: Session = Depends(get_db)):
    """
    Зарезервировать товары для B2C.
    """
    items = request.get("items", [])
    order_id = request.get("order_id")
    ttl_seconds = request.get("ttl_seconds", 900)
    
    results = []
    for item in items:
        sku_id = item["sku_id"]
        quantity = item["quantity"]
        
        sku = db.query(SKU).filter(SKU.id == sku_id).first()
        if not sku:
            results.append({
                "sku_id": sku_id,
                "requested": quantity,
                "reserved": 0,
                "available": 0,
                "error": "SKU not found"
            })
            continue
        
        available = sku.quantity - (sku.reserved_quantity or 0)
        reserved = min(quantity, available)
        
        if reserved > 0:
            # Создаем резерв
            reservation = SKUReservation(
                sku_id=sku_id,
                order_id=order_id,
                quantity=reserved,
                status="ACTIVE",
                expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds)
            )
            db.add(reservation)
            
            # Обновляем reserved_quantity в SKU
            sku.reserved_quantity = (sku.reserved_quantity or 0) + reserved
            db.add(sku)
        
        results.append({
            "sku_id": sku_id,
            "requested": quantity,
            "reserved": reserved,
            "available": available - reserved
        })
    
    db.commit()
    
    return {
        "reservation_id": str(uuid4()),
        "items": results
    }