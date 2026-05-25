# app/api/invoices.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.database import get_db
from app.models.invoice import Invoice, InvoiceItem   
from app.schemas.invoice import (
    InvoiceCreate, 
    InvoiceResponse, 
    InvoiceAcceptRequest,
    InvoiceItemResponse,
    InvoicePaginatedResponse
)
from app.models.sku import SKU 
from app.models.product import Product
from app.dependencies.auth import get_current_seller
from app.models.seller import Seller

router = APIRouter()


def error_response(code: str, message: str, status_code: int = 422):
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    invoice: InvoiceCreate,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Создать накладную на поступление товара.
    
    Валидация:
    - items должен содержать минимум 1 позицию
    - Все SKU должны существовать
    - Все SKU должны принадлежать текущему продавцу (IDOR check)
    - Все товары должны иметь статус MODERATED
    - quantity должно быть > 0
    """
    # 1. Проверка на пустой список
    if not invoice.items or len(invoice.items) == 0:
        error_response("INVALID_REQUEST", "At least one item is required", 400)
    
    # 2. Получаем все SKU одним запросом
    sku_ids = [item.sku_id for item in invoice.items]
    db_skus = db.query(SKU).filter(SKU.id.in_(sku_ids)).all()
    sku_map = {sku.id: sku for sku in db_skus}
    
    # Проверяем, что все SKU найдены
    for sku_id in sku_ids:
        if sku_id not in sku_map:
            error_response("NOT_FOUND", f"SKU {sku_id} not found", 404)
    
    # Проверяем ownership, статус товара и quantity
    for item in invoice.items:
        sku = sku_map[item.sku_id]
        
        # Проверка quantity
        if item.quantity <= 0:
            error_response("INVALID_REQUEST", "quantity must be > 0", 400)
        
        # Проверка ownership
        if sku.product.seller_id != current_seller.id:
            error_response("NOT_OWNER", "One or more SKUs do not belong to the authenticated seller", 403)
        
        # Проверка статуса товара
        if sku.product.status != "MODERATED":
            error_response("INVALID_REQUEST", "Invoice can only be created for MODERATED products", 400)
    
    # 3. Создаём накладную
    db_invoice = Invoice(
        seller_id=current_seller.id,
        status="CREATED"
    )
    db.add(db_invoice)
    db.flush()
    
    # 4. Создаём позиции
    for item in invoice.items:
        db_item = InvoiceItem(
            invoice_id=db_invoice.id,
            sku_id=item.sku_id,
            quantity=item.quantity,
            accepted_quantity=None
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_invoice)
    
    # 5. Формируем ответ
    db_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == db_invoice.id).all()
    return InvoiceResponse(
        id=db_invoice.id,
        seller_id=db_invoice.seller_id,
        status=db_invoice.status,
        created_at=db_invoice.created_at,
        updated_at=db_invoice.updated_at,
        accepted_at=db_invoice.accepted_at,
        items=[
            InvoiceItemResponse(
                id=inv_item.id,
                sku_id=inv_item.sku_id,
                quantity=inv_item.quantity,
                accepted_quantity=inv_item.accepted_quantity
            ) for inv_item in db_items
        ]
    )


@router.get("/", response_model=InvoicePaginatedResponse)
def get_invoices(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Получить список накладных текущего продавца с пагинацией"""
    # Считаем общее количество
    total_count = db.query(Invoice).filter(
        Invoice.seller_id == current_seller.id
    ).count()
    
    # Получаем накладные с пагинацией
    invoices = db.query(Invoice).filter(
        Invoice.seller_id == current_seller.id
    ).offset(offset).limit(limit).all()
    
    result_items = []
    for inv in invoices:
        items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).all()
        result_items.append(InvoiceResponse(
            id=inv.id,
            seller_id=inv.seller_id,
            status=inv.status,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
            accepted_at=inv.accepted_at,
            items=[
                InvoiceItemResponse(
                    id=item.id,
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    accepted_quantity=item.accepted_quantity
                ) for item in items
            ]
        ))
    
    return InvoicePaginatedResponse(
        items=result_items,
        total_count=total_count,
        limit=limit,
        offset=offset
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Получить накладную по ID (только свои)"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.seller_id == current_seller.id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Invoice not found"}
        )
    
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).all()
    return InvoiceResponse(
        id=invoice.id,
        seller_id=invoice.seller_id,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        accepted_at=invoice.accepted_at,
        items=[
            InvoiceItemResponse(
                id=item.id,
                sku_id=item.sku_id,
                quantity=item.quantity,
                accepted_quantity=item.accepted_quantity
            ) for item in items
        ]
    )


@router.post("/{invoice_id}/accept", response_model=InvoiceResponse)
def accept_invoice(
    invoice_id: UUID,
    accept_request: Optional[InvoiceAcceptRequest] = None,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Приёмка накладной (вызывается через Django Admin).
    
    Логика:
    - Если accepted_items не передан — принимается полностью (accepted_quantity = quantity для всех)
    - Если передан — для каждой позиции обновляем accepted_quantity
    - Увеличиваем active_quantity SKU на accepted_quantity
    - Определяем статус накладной:
      * Все accepted_quantity == quantity → ACCEPTED
      * Хотя бы один > 0, но не все полностью → PARTIALLY_ACCEPTED
      * Все accepted_quantity == 0 → REJECTED
    """
    # 1. Проверяем существование накладной
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Invoice not found"}
        )
    
    # 2. Проверяем, что накладная ещё не принята
    if invoice.status in ["ACCEPTED", "CANCELLED"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATE", "message": "Invoice cannot be accepted in current state"}
        )
    
    # 3. Получаем позиции накладной
    invoice_items = {item.id: item for item in invoice.items}
    
    # 4. Если accepted_items не передан — принимаем полностью
    if accept_request is None or not accept_request.accepted_items:
        for inv_item in invoice.items:
            inv_item.accepted_quantity = inv_item.quantity
            sku = db.query(SKU).filter(SKU.id == inv_item.sku_id).first()
            if sku:
                sku.active_quantity += inv_item.quantity
        
        invoice.status = "ACCEPTED"
        invoice.accepted_at = datetime.now(timezone.utc)
        invoice.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(invoice)
        
        db_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).all()
        return InvoiceResponse(
            id=invoice.id,
            seller_id=invoice.seller_id,
            status=invoice.status,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
            accepted_at=invoice.accepted_at,
            items=[
                InvoiceItemResponse(
                    id=item.id,
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    accepted_quantity=item.accepted_quantity
                ) for item in db_items
            ]
        )
    
    # 5. Валидируем и обрабатываем приёмку с accepted_items
    total_accepted = 0
    total_quantity = 0
    
    for accept_item in accept_request.accepted_items:
        if accept_item.invoice_item_id not in invoice_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": f"Invoice item {accept_item.invoice_item_id} not found"}
            )
        
        inv_item = invoice_items[accept_item.invoice_item_id]
        
        # Валидация accepted_quantity
        if accept_item.accepted_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "accepted_quantity must be >= 0"}
            )
        
        if accept_item.accepted_quantity > inv_item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": f"accepted_quantity cannot exceed quantity for invoice item {inv_item.id}"}
            )
        
        # Обновляем accepted_quantity
        inv_item.accepted_quantity = accept_item.accepted_quantity
        
        # Увеличиваем active_quantity SKU
        sku = db.query(SKU).filter(SKU.id == inv_item.sku_id).first()
        if sku:
            sku.active_quantity += accept_item.accepted_quantity
        
        # Считаем для определения статуса
        total_accepted += accept_item.accepted_quantity
        total_quantity += inv_item.quantity
    
    # 6. Определяем статус накладной
    if total_accepted == total_quantity:
        invoice.status = "ACCEPTED"
    elif total_accepted > 0:
        invoice.status = "PARTIALLY_ACCEPTED"
    else:
        invoice.status = "REJECTED"
    
    invoice.accepted_at = datetime.now(timezone.utc)
    invoice.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(invoice)
    
    # 7. Формируем ответ
    db_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).all()
    return InvoiceResponse(
        id=invoice.id,
        seller_id=invoice.seller_id,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        accepted_at=invoice.accepted_at,
        items=[
            InvoiceItemResponse(
                id=item.id,
                sku_id=item.sku_id,
                quantity=item.quantity,
                accepted_quantity=item.accepted_quantity
            ) for item in db_items
        ]
    )