from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.seller import Seller
from app.schemas.seller import (
    SellerResponse,
    SellerRegisterRequest,  
    SellerUpdateRequest     
)
from app.dependencies.auth import get_current_seller
from app.models.seller import Seller as SellerModel


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


def check_admin(current_seller: SellerModel):
    """Проверка прав администратора"""
    # TODO: добавить поле role или is_admin в модель Seller
    # Пока заглушка — только для внутреннего использования
    pass


router = APIRouter(prefix="/admin/sellers", tags=["Admin Sellers"])


@router.post("/", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
def create_seller(
    seller: SellerRegisterRequest,
    db: Session = Depends(get_db),
    current_seller: SellerModel = Depends(get_current_seller)
):
    """
    [ADMIN ONLY] Создать нового продавца.
    """
    # Проверка на дубликат ИНН
    existing = db.query(Seller).filter(Seller.inn == seller.inn).first()
    if existing:
        error_response("DUPLICATE_INN", "Seller with this INN already exists", 409)
    
    # Проверка на дубликат email
    existing_email = db.query(Seller).filter(Seller.email == seller.email).first()
    if existing_email:
        error_response("DUPLICATE_EMAIL", "Seller with this email already exists", 409)
    
    db_seller = Seller(
        email=seller.email,
        hashed_password=seller.hashed_password,  # TODO: хешировать пароль
        first_name=seller.first_name,
        last_name=seller.last_name,
        middle_name=seller.middle_name,
        company_name=seller.company_name,
        inn=seller.inn,
        phone=seller.phone,
        status="PENDING",
        is_active=True
    )
    db.add(db_seller)
    db.commit()
    db.refresh(db_seller)
    
    return SellerResponse(
        id=db_seller.id,
        email=db_seller.email,
        first_name=db_seller.first_name,
        last_name=db_seller.last_name,
        middle_name=db_seller.middle_name,
        company_name=db_seller.company_name,
        inn=db_seller.inn,
        phone=db_seller.phone,
        created_at=db_seller.created_at,
        updated_at=db_seller.updated_at
    )


@router.get("/", response_model=List[SellerResponse])
def get_sellers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_seller: SellerModel = Depends(get_current_seller)
):
    """
    [ADMIN ONLY] Получить список всех продавцов.
    """
    sellers = db.query(Seller).offset(skip).limit(limit).all()
    
    return [
        SellerResponse(
            id=s.id,
            email=s.email,
            first_name=s.first_name,
            last_name=s.last_name,
            middle_name=s.middle_name,
            company_name=s.company_name,
            inn=s.inn,
            phone=s.phone,
            created_at=s.created_at,
            updated_at=s.updated_at
        ) for s in sellers
    ]


@router.get("/{seller_id}", response_model=SellerResponse)
def get_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_seller: SellerModel = Depends(get_current_seller)
):
    """
    [ADMIN ONLY] Получить продавца по ID.
    """
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        error_response("NOT_FOUND", "Seller not found", 404)
    
    return SellerResponse(
        id=seller.id,
        email=seller.email,
        first_name=seller.first_name,
        last_name=seller.last_name,
        middle_name=seller.middle_name,
        company_name=seller.company_name,
        inn=seller.inn,
        phone=seller.phone,
        created_at=seller.created_at,
        updated_at=seller.updated_at
    )


@router.patch("/{seller_id}", response_model=SellerResponse)
def update_seller(
    seller_id: UUID,
    seller_update: SellerUpdateRequest,
    db: Session = Depends(get_db),
    current_seller: SellerModel = Depends(get_current_seller)
):
    """
    [ADMIN ONLY] Обновить данные продавца.
    """
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        error_response("NOT_FOUND", "Seller not found", 404)
    
    update_data = seller_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(seller, field, value)
    
    db.commit()
    db.refresh(seller)
    
    return SellerResponse(
        id=seller.id,
        email=seller.email,
        first_name=seller.first_name,
        last_name=seller.last_name,
        middle_name=seller.middle_name,
        company_name=seller.company_name,
        inn=seller.inn,
        phone=seller.phone,
        created_at=seller.created_at,
        updated_at=seller.updated_at
    )


@router.delete("/{seller_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_seller: SellerModel = Depends(get_current_seller)
):
    """
    [ADMIN ONLY] Удалить продавца (soft-delete).
    """
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        error_response("NOT_FOUND", "Seller not found", 404)
    
    seller.is_active = False
    db.commit()
    return None