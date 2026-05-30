from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.seller import Seller
from app.schemas.seller import (
    SellerResponse,
    SellerCreate,
    SellerUpdate
)
from app.schemas.common import PaginatedResponse
from app.dependencies.auth import get_current_seller, check_admin
from app.core.security import hash_password

router = APIRouter(prefix="/admin/sellers", tags=["Admin Sellers"])


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


class PaginatedSellers(PaginatedResponse):
    items: List[SellerResponse]


@router.post("/", response_model=SellerResponse, status_code=status.HTTP_201_CREATED)
def create_seller(
    seller: SellerCreate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Создать нового продавца - POST /api/v1/admin/sellers/"""
    check_admin(current_seller)
    
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
        hashed_password=hash_password(seller.password),  # ← хешируем пароль
        first_name=seller.first_name,
        last_name=seller.last_name,
        middle_name=seller.middle_name,
        company_name=seller.company_name,
        inn=seller.inn,
        phone=seller.phone,
        status="PENDING",
        is_active=True,
        role="SELLER"  # ← по умолчанию обычный продавец
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


@router.get("/", response_model=PaginatedSellers)
def get_sellers(
    limit: int = 20,
    offset: int = 0,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Получить список всех продавцов - GET /api/v1/admin/sellers/"""
    check_admin(current_seller)
    
    query = db.query(Seller)
    
    if is_active is not None:
        query = query.filter(Seller.is_active == is_active)
    
    total = query.count()
    sellers = query.order_by(Seller.created_at.desc()).offset(offset).limit(limit).all()
    
    return PaginatedSellers(
        items=[
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
        ],
        total_count=total,
        limit=limit,
        offset=offset
    )


@router.get("/{seller_id}", response_model=SellerResponse)
def get_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Получить продавца по ID - GET /api/v1/admin/sellers/{seller_id}"""
    check_admin(current_seller)
    
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
    seller_update: SellerUpdate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Обновить данные продавца - PATCH /api/v1/admin/sellers/{seller_id}"""
    check_admin(current_seller)
    
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
    current_seller: Seller = Depends(get_current_seller)
):
    """[ADMIN ONLY] Удалить продавца (soft-delete) - DELETE /api/v1/admin/sellers/{seller_id}"""
    check_admin(current_seller)
    
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        error_response("NOT_FOUND", "Seller not found", 404)
    
    seller.is_active = False
    db.commit()
    return None