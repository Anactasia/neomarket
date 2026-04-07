# app/api/invoices.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.invoice import Invoice, InvoiceItem   
from app.schemas.invoice import Invoice as InvoiceSchema, InvoiceCreate
from app.models.sku import SKU 

router = APIRouter()

@router.post("/", response_model=InvoiceSchema, status_code=status.HTTP_201_CREATED)
def create_invoice(invoice: InvoiceCreate, db: Session = Depends(get_db)):

    db_invoice = Invoice(
        seller_id=invoice.seller_id,
        invoice_number=invoice.invoice_number,
        warehouse_id=invoice.warehouse_id,
        status="CREATED"
    )
    db.add(db_invoice)
    db.flush()  # 🔥 ВАЖНО (получаем ID без commit)

    # 🔥 СОЗДАЁМ ITEMS
    for item in invoice.items:
        db_item = InvoiceItem(
            invoice_id=db_invoice.id,
            sku_id=item.sku_id,
            quantity=item.quantity
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_invoice)

    return db_invoice

@router.get("/", response_model=List[InvoiceSchema])
def get_invoices(
    skip: int = 0,
    limit: int = 100,
    seller_id: UUID = None,
    db: Session = Depends(get_db)
):
    """
    Получить список накладных.
    - **seller_id**: фильтр по продавцу
    """
    query = db.query(Invoice)
    if seller_id:
        query = query.filter(Invoice.seller_id == seller_id)
    
    invoices = query.offset(skip).limit(limit).all()
    return invoices

@router.get("/{invoice_id}", response_model=InvoiceSchema)
def get_invoice(invoice_id: UUID, db: Session = Depends(get_db)):
    """Получить накладную по ID"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Накладная не найдена"
        )
    return invoice

@router.post("/{invoice_id}/accept", response_model=InvoiceSchema)
def accept_invoice(invoice_id: UUID, db: Session = Depends(get_db)):

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Накладная не найдена"
        )

    # 🔥 ОБНОВЛЯЕМ ОСТАТКИ SKU
    for item in invoice.items:
        sku = db.query(SKU).filter(SKU.id == item.sku_id).first()
        if sku:
            sku.quantity += item.quantity

    invoice.status = "ACCEPTED"

    db.commit()
    db.refresh(invoice)
    return invoice