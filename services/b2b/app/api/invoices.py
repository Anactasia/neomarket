from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
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
    """
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
        
        if sku.product.status != "MODERATED":
            error_response("INVALID_REQUEST", "Invoice can only be created for MODERATED products", 400)
    
    # 3. Создаём накладную
    db_invoice = Invoice(
        seller_id=current_seller.id,
        status=InvoiceStatus.CREATED
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


@router.get("/", response_model=InvoicePaginatedResponse)
def get_invoices(
    limit: int = 20,
    offset: int = 0,
    status_filter: Optional[InvoiceStatus] = None,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Получить список накладных текущего продавца с пагинацией и фильтром по статусу"""
    query = db.query(Invoice).filter(Invoice.seller_id == current_seller.id)
    
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    
    total_count = query.count()
    invoices = query.options(selectinload(Invoice.items)).offset(offset).limit(limit).all()
    
    result_items = []
    for inv in invoices:
        result_items.append(InvoiceResponse(
            id=inv.id,
            seller_id=inv.seller_id,
            status=inv.status,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
            accepted_at=inv.accepted_at,
            accepted_by=inv.accepted_by_id,
            items=[
                InvoiceItemResponse(
                    id=item.id,
                    sku_id=item.sku_id,
                    quantity=item.quantity,
                    accepted_quantity=item.accepted_quantity
                ) for item in inv.items  
            ]
        ))
    
    return InvoicePaginatedResponse(
        items=result_items,
        total_count=total_count,
        limit=limit,
        offset=offset
    )


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Удалить накладную (только в статусе CREATED)"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.seller_id == current_seller.id
    ).first()
    
    if not invoice:
        error_response("NOT_FOUND", "Invoice not found", 404)
    
    if invoice.status != InvoiceStatus.CREATED:
        error_response("INVALID_STATE", "Invoice can only be deleted in CREATED status", 409)
    
    db.delete(invoice)
    db.commit()
    return None


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """Получить накладную по ID (только свои)"""
    invoice = db.query(Invoice).options(selectinload(Invoice.items)).filter(
        Invoice.id == invoice_id,
        Invoice.seller_id == current_seller.id
    ).first()
    
    if not invoice:
        error_response("NOT_FOUND", "Invoice not found", 404)
    
    return InvoiceResponse(
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


@router.post("/{invoice_id}/accept", response_model=InvoiceResponse)
def accept_invoice(
    invoice_id: UUID,
    accept_request: Optional[InvoiceAcceptRequest] = None,
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    # 1. Загружаем накладную с items (selectinload) + проверка владельца
    invoice = db.query(Invoice).options(selectinload(Invoice.items)).filter(
        Invoice.id == invoice_id,
        Invoice.seller_id == current_seller.id
    ).first()
    if not invoice:
        error_response("NOT_FOUND", "Invoice not found", 404)
    
    # 2. Проверка статуса
    if invoice.status in [InvoiceStatus.ACCEPTED, InvoiceStatus.PARTIALLY_ACCEPTED, InvoiceStatus.CANCELLED]:
        error_response("INVALID_STATE", "Invoice cannot be accepted", 409)
    
    # 3. Загружаем все SKU одним запросом (решаем N+1)
    all_sku_ids = [item.sku_id for item in invoice.items]
    skus = {sku.id: sku for sku in db.query(SKU).filter(SKU.id.in_(all_sku_ids)).all()}
    
    # 4. Полная приёмка (если accept_request не передан или accepted_items пуст)
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
        
        return InvoiceResponse(
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
        # accepted_at НЕ обновляем при частичной приёмке
    
    invoice.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)
    
    return InvoiceResponse(
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