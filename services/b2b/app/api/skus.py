# app/api/skus.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.sku import SKU

from app.schemas.sku import (
    SKU as SKUSchema,
    SKUCreateWithValidation,
    SKUUpdateWithValidation
)

router = APIRouter(prefix="/skus", tags=["SKU"])

@router.post("/", response_model=SKUSchema, status_code=status.HTTP_201_CREATED)
def create_sku(sku: SKUCreateWithValidation, db: Session = Depends(get_db)):
    """
    Создать новый SKU (вариант товара).
    - **product_id**: ID товара
    - **name**: название варианта
    - **price**: цена в копейках
    - **quantity**: количество на складе
    """
    db_sku = SKU(**sku.dict())
    db.add(db_sku)
    db.commit()
    db.refresh(db_sku)
    return db_sku

@router.get("/", response_model=List[SKUSchema])
def get_skus(
    skip: int = 0,
    limit: int = 100,
    product_id: int = None,
    db: Session = Depends(get_db)
):
    """
    Получить список SKU.
    - **product_id**: фильтр по товару
    """
    query = db.query(SKU)
    if product_id:
        query = query.filter(SKU.product_id == product_id)
    
    skus = query.offset(skip).limit(limit).all()
    return skus

@router.get("/{sku_id}", response_model=SKUSchema)
def get_sku(sku_id: int, db: Session = Depends(get_db)):
    """Получить SKU по ID"""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SKU не найден"
        )
    return sku

@router.put("/{sku_id}", response_model=SKUSchema)
def update_sku(
    sku_id: int,
    sku_update: SKUUpdateWithValidation,
    db: Session = Depends(get_db)
):
    """Обновить SKU"""
    sku = db.query(SKU).filter(SKU.id == sku_id).first()
    if not sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SKU не найден"
        )
    
    for field, value in sku_update.dict(exclude_unset=True).items():
        setattr(sku, field, value)
    
    db.commit()
    db.refresh(sku)
    return sku

@router.delete("/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sku(sku_id: int, db: Session = Depends(get_db)):
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