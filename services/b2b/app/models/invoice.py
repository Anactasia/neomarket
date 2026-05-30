# app/models/invoice.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
from enum import Enum
import uuid


class InvoiceStatus(str, Enum):
    CREATED = "CREATED"
    PARTIALLY_ACCEPTED = "PARTIALLY_ACCEPTED"
    ACCEPTED = "ACCEPTED"
    CANCELLED = "CANCELLED"


class Invoice(BaseModel):
    __tablename__ = "invoices"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    seller_id = Column(GUID, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default=InvoiceStatus.CREATED.value)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_id = Column(GUID, ForeignKey("sellers.id", ondelete="SET NULL"), nullable=True)
    
    # Индексы
    __table_args__ = (
        Index('ix_invoices_seller_id', 'seller_id'),
        Index('ix_invoices_status', 'status'),
        Index('ix_invoices_created_at', 'created_at'),
        Index('ix_invoices_accepted_at', 'accepted_at'),
    )
    
    # Relationships
    seller = relationship("Seller", foreign_keys=[seller_id], back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    accepted_by = relationship("Seller", foreign_keys=[accepted_by_id])


class InvoiceItem(BaseModel):
    __tablename__ = "invoice_items"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    invoice_id = Column(GUID, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    sku_id = Column(GUID, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    accepted_quantity = Column(Integer, nullable=False, default=0)  # ← исправлено
    
    # Индексы
    __table_args__ = (
        Index('ix_invoice_items_invoice_id', 'invoice_id'),
        Index('ix_invoice_items_sku_id', 'sku_id'),
    )
    
    # Relationships
    invoice = relationship("Invoice", back_populates="items")
    sku = relationship("SKU")