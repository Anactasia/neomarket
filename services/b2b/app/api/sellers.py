from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.seller import Seller
from app.schemas.seller import SellerResponse
from app.dependencies.auth import get_current_seller

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


# ─── ME endpoints (IDOR-safe, id из JWT) ───

@router.get("/me", response_model=SellerResponse)
def get_my_seller_profile(
    current_seller: Seller = Depends(get_current_seller)
):
    """Профиль текущего продавца"""
    return SellerResponse(
        id=current_seller.id,
        email=current_seller.email,
        first_name=current_seller.first_name,
        last_name=current_seller.last_name,
        middle_name=current_seller.middle_name,
        company_name=current_seller.company_name,
        inn=current_seller.inn,
        phone=current_seller.phone,
        created_at=current_seller.created_at,
        updated_at=current_seller.updated_at
    )


@router.patch("/me", response_model=SellerResponse)
def update_my_seller_profile(
    seller_update: dict,  # TODO: использовать SellerUpdateRequest
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Обновить профиль текущего продавца"""
    # TODO: валидация полей
    for field, value in seller_update.items():
        if hasattr(current_seller, field) and value is not None:
            setattr(current_seller, field, value)
    
    db.commit()
    db.refresh(current_seller)
    
    return SellerResponse(
        id=current_seller.id,
        email=current_seller.email,
        first_name=current_seller.first_name,
        last_name=current_seller.last_name,
        middle_name=current_seller.middle_name,
        company_name=current_seller.company_name,
        inn=current_seller.inn,
        phone=current_seller.phone,
        created_at=current_seller.created_at,
        updated_at=current_seller.updated_at
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_seller_account(
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Удалить аккаунт продавца (soft-delete)"""
    if not current_seller.is_active:
        error_response("INVALID_REQUEST", "Account already deleted", 400)
    
    current_seller.is_active = False
    db.commit()
    return None