from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.seller import Seller
from app.schemas.seller import SellerRegisterRequest, SellerLoginRequest, RefreshRequest
from app.schemas.auth import TokenResponse
from app.core.security import (
    get_password_hash, verify_password, 
    create_access_token, create_refresh_token, decode_token
)
from app.dependencies.auth import get_current_seller

router = APIRouter(tags=["Auth"])  # префикс из основного роутера


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    seller_data: SellerRegisterRequest,
    db: Session = Depends(get_db)
):
    """POST /api/v1/auth/register - регистрация продавца"""
    
    existing = db.query(Seller).filter(Seller.email == seller_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "Email already registered"}
        )
    
    existing_inn = db.query(Seller).filter(Seller.inn == seller_data.inn).first()
    if existing_inn:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INN_EXISTS", "message": "INN already registered"}
        )
    
    db_seller = Seller(
        email=seller_data.email,
        hashed_password=get_password_hash(seller_data.password),
        first_name=seller_data.first_name,
        last_name=seller_data.last_name,
        middle_name=seller_data.middle_name,
        company_name=seller_data.company_name,
        inn=seller_data.inn,
        phone=seller_data.phone,
        status="PENDING",
        is_active=True
    )
    
    db.add(db_seller)
    db.commit()
    db.refresh(db_seller)
    
    access_token = create_access_token(data={"sub": str(db_seller.id)})
    refresh_token = create_refresh_token(data={"sub": str(db_seller.id)})
    
    return TokenResponse(
        user_id=db_seller.id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        token_type="Bearer"
    )


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: SellerLoginRequest,
    db: Session = Depends(get_db)
):
    """POST /api/v1/auth/login - логин продавца"""
    
    seller = db.query(Seller).filter(Seller.email == login_data.email).first()
    if not seller or not verify_password(login_data.password, seller.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not seller.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "Account is disabled"},
        )
    
    access_token = create_access_token(data={"sub": str(seller.id)})
    refresh_token = create_refresh_token(data={"sub": str(seller.id)})
    
    return TokenResponse(
        user_id=seller.id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600,
        token_type="Bearer"
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(refresh_data: RefreshRequest):
    """POST /api/v1/auth/refresh - обновление access токена"""
    
    payload = decode_token(refresh_data.refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid refresh token"}
        )
    
    seller_id = payload.get("sub")
    if not seller_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid token payload"}
        )
    
    new_access_token = create_access_token(data={"sub": seller_id})
    new_refresh_token = create_refresh_token(data={"sub": seller_id})
    
    return TokenResponse(
        user_id=UUID(seller_id),
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=3600,
        token_type="Bearer"
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_seller: Seller = Depends(get_current_seller)):
    """POST /api/v1/auth/logout - выход (отзыв refresh токена)"""
    # TODO: добавить refresh токен в черный список
    return None