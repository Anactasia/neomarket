# app/models/seller.py
from sqlalchemy import Column, String, DECIMAL, Boolean, DateTime, Text, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
from enum import Enum
import uuid
from datetime import datetime


class SellerStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


class Seller(BaseModel):
    __tablename__ = "sellers"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    
    # Аутентификация
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Информация о компании
    company_name = Column(String(255), nullable=False)
    inn = Column(String(12), unique=True, nullable=False)
    kpp = Column(String(9), nullable=True)
    ogrn = Column(String(15), nullable=True)
    legal_address = Column(String(500), nullable=True)
    actual_address = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Контактное лицо
    first_name = Column(String(100), nullable=False)  # ← убран default
    last_name = Column(String(100), nullable=False)   # ← убран default
    middle_name = Column(String(100), nullable=True)
    
    # Статусы
    status = Column(String(20), default=SellerStatus.PENDING.value)
    rating = Column(DECIMAL(3, 2), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Индексы
    __table_args__ = (
        Index('ix_sellers_email', 'email'),
        Index('ix_sellers_inn', 'inn'),
        Index('ix_sellers_status', 'status'),
        Index('ix_sellers_is_active', 'is_active'),
        Index('ix_sellers_created_at', 'created_at'),
    )
    
    # Relationships
    products = relationship("Product", back_populates="seller")
    invoices = relationship("Invoice", foreign_keys="Invoice.seller_id", back_populates="seller")
    accepted_invoices = relationship("Invoice", foreign_keys="Invoice.accepted_by_id", back_populates="accepted_by")
    
    @property
    def full_name(self) -> str:
        """Полное имя контактного лица"""
        if self.middle_name:
            return f"{self.first_name} {self.last_name} {self.middle_name}"
        return f"{self.first_name} {self.last_name}"