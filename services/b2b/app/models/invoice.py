# app/models/invoice.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid

class Invoice(BaseModel):
    __tablename__ = "invoices"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    seller_id = Column(GUID, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="CREATED")  # CREATED, PARTIALLY_ACCEPTED, ACCEPTED, CANCELLED
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_id = Column(GUID, ForeignKey("sellers.id", ondelete="SET NULL"), nullable=True)  # Оператор-админ, принявший накладную
    
    seller = relationship("Seller", foreign_keys=[seller_id], back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    accepted_by = relationship("Seller", foreign_keys=[accepted_by_id])
    

class InvoiceItem(BaseModel):
    __tablename__ = "invoice_items"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    invoice_id = Column(GUID, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)    
    sku_id = Column(GUID, ForeignKey("skus.id"), nullable=False) 
    quantity = Column(Integer, nullable=False)
    accepted_quantity = Column(Integer, nullable=True)
    
    invoice = relationship("Invoice", back_populates="items")
    sku = relationship("SKU")