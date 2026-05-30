from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.invoice import Invoice, InvoiceItem   
from app.schemas.invoice import (
    InvoiceCreate, 
    InvoiceResponse, 
    InvoiceAcceptRequest,
    InvoiceItemResponse,
    InvoicePaginatedResponse,
    InvoiceStatus
)
from app.models.sku import SKU 
from app.models.product import Product
from app.schemas.product import ProductStatus
from app.dependencies.auth import get_current_seller
from app.models.seller import Seller

router = APIRouter()

# Временный кэш для идемпотентности (TTL 1 час)
# В production заменить на Redis
_idempotency_cache: dict[str, dict] = {}


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _clean_expired_cache():
    """Очищает устаревшие записи из кэша"""
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _idempotency_cache.items() if v["expires_at"] < now]
    for k in expired:
        del _idempotency_cache[k]


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice: InvoiceCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Создать накладную на поступление товара - POST /api/v1/invoices/
    
    Idempotency-Key: обязательный заголовок для защиты от дублей (TTL 1 час)
    """
    _clean_expired_cache()
    
    # Проверка идемпотентности
    cache_key = f"invoice:create:{current_seller.id}:{idempotency_key}"
    if cache_key in _idempotency_cache:
        cached = _idempotency_cache[cache_key]
        return cached["response"]
    
    # 1. Проверка на пустой список
    if not invoice.items or len(invoice.items) == 0:
        error_response("INVALID_REQUEST", "At least one item is required", 400)
    
    # 2. Получаем все SKU одним запросом
    sku_ids = [item.sku_id for item in invoice.items]
    
    if len(sku_ids) != len(set(sku_ids)):
        error_response("INVALID_REQUEST", "Duplicate SKU IDs in items", 400)
    
    db_skus = db.query(SKU).filter(SKU.id.in_(sku_ids)).all()
    sku_map = {sku.id: sku for sku in db_skus}
    
    # Проверяем, что все SKU найдены
    for sku_id in sku_ids:
        if sku_id not in sku_map:
            error_response("NOT_FOUND", f"SKU {sku_id} not found", 404)
    
    # Проверяем ownership, статус товара и quantity
    for item in invoice.items:
        sku = sku_map[item.sku_id]
        
        if item.quantity <= 0:
            error_response("INVALID_REQUEST", "quantity must be > 0", 400)
        
        if sku.product.seller_id != current_seller.id:
            error_response("NOT_OWNER", "One or more SKUs do not belong to the authenticated seller", 403)
        
        if sku.product.status != ProductStatus.MODERATED.value:
            error_response("INVALID_REQUEST", "Invoice can only be created for MODERATED products", 400)
    
    # 3. Создаём накладную
    db_invoice = Invoice(
        seller_id=current_seller.id,
        status=InvoiceStatus.CREATED
    )
    db.add(db_invoice)
    db.flush()
    
    # 4. Создаём позиции (accepted_quantity = 0 по умолчанию)
    for item in invoice.items:
        db_item = InvoiceItem(
            invoice_id=db_invoice.id,
            sku_id=item.sku_id,
            quantity=item.quantity,
            accepted_quantity=0
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_invoice)
    
    # 5. Формируем ответ
    db_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == db_invoice.id).all()
    response_data = InvoiceResponse(
        id=db_invoice.id,
        seller_id=db_invoice.seller_id,
        status=db_invoice.status,
        created_at=db_invoice.created_at,
        updated_at=db_invoice.updated_at,
        accepted_at=db_invoice.accepted_at,
        accepted_by=db_invoice.accepted_by_id,
        items=[
            InvoiceItemResponse(
                id=inv_item.id,
                sku_id=inv_item.sku_id,
                quantity=inv_item.quantity,
                accepted_quantity=inv_item.accepted_quantity
            ) for inv_item in db_items
        ]
    )
    
    # Сохраняем в кэш
    _idempotency_cache[cache_key] = {
        "response": response_data,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    return response_data


# Остальные эндпоинты (GET, DELETE, GET /{id}) остаются без изменений
# ...


@router.post("/{invoice_id}/accept", response_model=InvoiceResponse)
def accept_invoice(
    invoice_id: UUID,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    accept_request: Optional[InvoiceAcceptRequest] = None,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Приёмка накладной - POST /api/v1/invoices/{invoice_id}/accept
    
    Idempotency-Key: обязательный заголовок для защиты от дублей (TTL 1 час)
    """
    _clean_expired_cache()
    
    # Проверка идемпотентности
    cache_key = f"invoice:accept:{current_seller.id}:{invoice_id}:{idempotency_key}"
    if cache_key in _idempotency_cache:
        cached = _idempotency_cache[cache_key]
        return cached["response"]
    
    # 1. Загружаем накладную с items
    invoice = db.query(Invoice).options(selectinload(Invoice.items)).filter(
        Invoice.id == invoice_id,
        Invoice.seller_id == current_seller.id
    ).first()
    if not invoice:
        error_response("NOT_FOUND", "Invoice not found", 404)
    
    # 2. Проверка статуса
    if invoice.status in [InvoiceStatus.ACCEPTED, InvoiceStatus.PARTIALLY_ACCEPTED, InvoiceStatus.CANCELLED]:
        error_response("INVALID_STATE", "Invoice cannot be accepted", 409)
    
    # 3. Загружаем все SKU одним запросом
    all_sku_ids = [item.sku_id for item in invoice.items]
    skus = {sku.id: sku for sku in db.query(SKU).filter(SKU.id.in_(all_sku_ids)).all()}
    
    # 4. Полная приёмка
    if accept_request is None or not accept_request.accepted_items:
        for inv_item in invoice.items:
            inv_item.accepted_quantity = inv_item.quantity
            sku = skus.get(inv_item.sku_id)
            if sku:
                sku.active_quantity += inv_item.quantity
        
        invoice.status = InvoiceStatus.ACCEPTED
        invoice.accepted_at = datetime.now(timezone.utc)
        invoice.accepted_by_id = current_seller.id
        invoice.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(invoice)
        
        response_data = InvoiceResponse(
            id=invoice.id,
            seller_id=invoice.seller_id,
            status=invoice.status,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
            accepted_at=invoice.accepted_at,
            accepted_by=invoice.accepted_by_id,
            items=[
                InvoiceItemResponse(
                    id=item.id,
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    accepted_quantity=item.accepted_quantity
                ) for item in invoice.items
            ]
        )
        
        # Сохраняем в кэш
        _idempotency_cache[cache_key] = {
            "response": response_data,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        
        return response_data
    
    # 5. Частичная приёмка
    total_accepted = 0
    total_quantity = 0
    invoice_items = {item.id: item for item in invoice.items}
    
    for accept_item in accept_request.accepted_items:
        if accept_item.invoice_item_id not in invoice_items:
            error_response("INVALID_REQUEST", f"Invoice item {accept_item.invoice_item_id} not found", 400)
        
        inv_item = invoice_items[accept_item.invoice_item_id]
        
        if accept_item.accepted_quantity < 0 or accept_item.accepted_quantity > inv_item.quantity:
            error_response("INVALID_REQUEST", f"Invalid accepted_quantity for {inv_item.id}", 400)
        
        inv_item.accepted_quantity = accept_item.accepted_quantity
        
        sku = skus.get(inv_item.sku_id)
        if sku:
            sku.active_quantity += accept_item.accepted_quantity
        
        total_accepted += accept_item.accepted_quantity
        total_quantity += inv_item.quantity
    
    # 6. Проверка, что хоть что-то принято
    if total_accepted == 0:
        error_response("INVALID_REQUEST", "At least one item must be accepted", 400)
    
    # 7. Определяем статус
    if total_accepted == total_quantity:
        invoice.status = InvoiceStatus.ACCEPTED
        invoice.accepted_at = datetime.now(timezone.utc)
        invoice.accepted_by_id = current_seller.id
    else:
        invoice.status = InvoiceStatus.PARTIALLY_ACCEPTED
    
    invoice.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)
    
    response_data = InvoiceResponse(
        id=invoice.id,
        seller_id=invoice.seller_id,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        accepted_at=invoice.accepted_at,
        accepted_by=invoice.accepted_by_id,
        items=[
            InvoiceItemResponse(
                id=item.id,
                sku_id=item.sku_id,
                quantity=item.quantity,
                accepted_quantity=item.accepted_quantity
            ) for item in invoice.items
        ]
    )
    
    # Сохраняем в кэш
    _idempotency_cache[cache_key] = {
        "response": response_data,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    
    return response_data