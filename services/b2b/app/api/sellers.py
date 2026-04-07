# app/api/sellers.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.seller import Seller

from app.schemas.seller import (
    Seller as SellerSchema,
    SellerCreateWithValidation,
    SellerUpdateWithValidation
)

router = APIRouter()

@router.post("/", response_model=SellerSchema, status_code=status.HTTP_201_CREATED)
def create_seller(seller: SellerCreateWithValidation, db: Session = Depends(get_db)):
    """
    Создать нового продавца.
    - **company_name**: название компании
    - **inn**: ИНН (уникальный)
    - **email**: email компании
    """
    # Проверяем, есть ли уже продавец с таким ИНН
    existing = db.query(Seller).filter(Seller.inn == seller.inn).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Продавец с таким ИНН уже существует"
        )
    
    db_seller = Seller(**seller.model_dump(), status="PENDING")
    db.add(db_seller)
    db.commit()
    db.refresh(db_seller)
    return db_seller

@router.get("/", response_model=List[SellerSchema])
def get_sellers(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Получить список всех продавцов.
    - **skip**: сколько пропустить
    - **limit**: сколько вернуть
    """
    sellers = db.query(Seller).offset(skip).limit(limit).all()
    return sellers

@router.get("/{seller_id}", response_model=SellerSchema)
def get_seller(seller_id: UUID, db: Session = Depends(get_db)):
    """
    Получить продавца по ID.
    """
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Продавец не найден"
        )
    return seller

@router.put("/{seller_id}", response_model=SellerSchema)
def update_seller(
    seller_id: UUID,
    seller_update: SellerUpdateWithValidation,
    db: Session = Depends(get_db)
):
    """
    Обновить данные продавца.
    """
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Продавец не найден"
        )
    
    for field, value in seller_update.model_dump(exclude_unset=True).items():
        setattr(seller, field, value)
    
    db.commit()
    db.refresh(seller)
    return seller