# app/models/seller.py
from sqlalchemy import Column, String, DECIMAL, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import uuid

class Seller(BaseModel):
    __tablename__ = "sellers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name = Column(String(255), nullable=False)
    inn = Column(String(12), unique=True, nullable=False)
    kpp = Column(String(9))
    ogrn = Column(String(15))
    legal_address = Column(String(500))
    actual_address = Column(String(500))
    phone = Column(String(20))
    email = Column(String(255))
    status = Column(String(20), default="PENDING")  # PENDING, ACTIVE, BLOCKED
    rating = Column(DECIMAL(3, 2), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    products = relationship("Product", back_populates="seller")
    invoices = relationship("Invoice", back_populates="seller")