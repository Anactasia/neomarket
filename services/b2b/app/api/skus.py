# app/api/skus.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.sku import SKU
from app.models.product import Product

from app.schemas.sku import (
    SKU as SKUSchema,
    SKUCreateWithValidation,
    SKUUpdateWithValidation
)

router = APIRouter()

@router.post("/", response_model=SKUSchema, status_code=status.HTTP_201_CREATED)
def create_sku(sku: SKUCreateWithValidation, db: Session = Depends(get_db)):
    """
    Создать новый SKU (вариант товара).
    - **product_id**: ID товара
    - **name**: название варианта
    - **price**: цена в копейках
    - **quantity**: количество на складе
    """
    product = db.query(Product).filter(Product.id == sku.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    db_sku = SKU(**sku.model_dump())

    db.add(db_sku)
    db.commit()
    db.refresh(db_sku)

    return db_sku

@router.get("/", response_model=List[SKUSchema])
def get_skus(
    skip: int = 0,
    limit: int = 100,
    product_id: UUID = None,
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
def get_sku(sku_id: UUID, db: Session = Depends(get_db)):
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
    sku_id: UUID,
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
    
    for field, value in sku_update.model_dump(exclude_unset=True).items():
        setattr(sku, field, value)
    
    db.commit()
    db.refresh(sku)
    return sku

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