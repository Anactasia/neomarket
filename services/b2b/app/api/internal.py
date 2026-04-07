# app/api/internal.py (создать)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.product import Product
from uuid import UUID

router = APIRouter()

@router.post("/moderation-callback")
def moderation_callback(
    callback: dict,
    db: Session = Depends(get_db)
):
    """
    Получить результат модерации от Moderation сервиса.
    """
    product_id = callback.get("product_id")
    decision = callback.get("decision")  # APPROVED or DECLINED
    comment = callback.get("comment")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if decision == "APPROVED":
        product.status = "MODERATED"
        product.published_at = datetime.utcnow()
    else:
        product.status = "BLOCKED"
        product.moderation_comment = comment
    
    db.commit()
    
    return {
        "success": True,
        "product_id": product_id,
        "new_status": product.status
    }