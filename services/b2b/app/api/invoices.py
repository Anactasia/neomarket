# app/api/invoices.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.invoice import Invoice
from app.schemas.invoice import Invoice as InvoiceSchema, InvoiceCreate

router = APIRouter(prefix="/invoices", tags=["Накладные"])

@router.post("/", response_model=InvoiceSchema, status_code=status.HTTP_201_CREATED)
def create_invoice(invoice: InvoiceCreate, db: Session = Depends(get_db)):
    """
    Создать новую накладную.
    - **seller_id**: ID продавца
    - **invoice_number**: номер накладной
    - **items**: список товаров
    """
    db_invoice = Invoice(
        seller_id=str(invoice.seller_id),
        invoice_number=invoice.invoice_number,
        warehouse_id=invoice.warehouse_id,
        status="CREATED"
    )
    db.add(db_invoice)
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
        query = query.filter(Invoice.seller_id == str(seller_id))
    
    invoices = query.offset(skip).limit(limit).all()
    return invoices

@router.get("/{invoice_id}", response_model=InvoiceSchema)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Получить накладную по ID"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Накладная не найдена"
        )
    return invoice

@router.post("/{invoice_id}/accept", response_model=InvoiceSchema)
def accept_invoice(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """Принять накладную"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Накладная не найдена"
        )
    
    invoice.status = "ACCEPTED"
    db.commit()
    db.refresh(invoice)
    return invoice