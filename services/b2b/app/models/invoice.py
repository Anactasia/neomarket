# app/models/invoice.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, DECIMAL, UniqueConstraint 
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid

class Invoice(BaseModel):
    __tablename__ = "invoices"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    seller_id = Column(GUID, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    invoice_number = Column(String(50), nullable=False)
    status = Column(String(20), default="CREATED")  # CREATED, ACCEPTED, REJECTED, CANCELLED
    warehouse_id = Column(Integer, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    
    seller = relationship("Seller", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('seller_id', 'invoice_number', name='unique_seller_invoice'),
    )

class InvoiceItem(BaseModel):
    __tablename__ = "invoice_items"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    invoice_id = Column(GUID, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)    
    sku_id = Column(GUID, ForeignKey("skus.id"), nullable=False) 
    quantity = Column(Integer, nullable=False)
    price = Column(Integer) 
    accepted_quantity = Column(Integer)
    
    invoice = relationship("Invoice", back_populates="items")
    sku = relationship("SKU")