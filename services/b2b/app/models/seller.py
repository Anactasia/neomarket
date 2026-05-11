from sqlalchemy import Column, String, DECIMAL, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid
from datetime import datetime


class Seller(BaseModel):
    __tablename__ = "sellers"
    
    # Основной ID
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    
    # Аутентификация (ДОБАВИТЬ)
    email = Column(String(255), unique=True, nullable=False, index=True)  # ← переместить сюда
    hashed_password = Column(String(255), nullable=False)  # ← добавить
    
    # Информация о компании (существующие поля)
    company_name = Column(String(255), nullable=False)
    inn = Column(String(12), unique=True, nullable=False)
    kpp = Column(String(9), nullable=True)
    ogrn = Column(String(15), nullable=True)
    legal_address = Column(String(500), nullable=True)
    actual_address = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Контактное лицо (ДОБАВИТЬ для регистрации)
    first_name = Column(String(100), nullable=False, default="")  # ← добавить
    last_name = Column(String(100), nullable=False, default="")   # ← добавить
    middle_name = Column(String(100), nullable=True)               # ← добавить
    
    # Статусы
    status = Column(String(20), default="PENDING")  # PENDING, ACTIVE, BLOCKED
    rating = Column(DECIMAL(3, 2), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Флаг активности (для аутентификации)
    is_active = Column(Boolean, default=True)  # ← добавить
    
    # Связи
    products = relationship("Product", back_populates="seller")
    invoices = relationship("Invoice", back_populates="seller")
    
    @property
    def full_name(self) -> str:
        """Полное имя контактного лица"""
        if self.middle_name:
            return f"{self.first_name} {self.last_name} {self.middle_name}"
        return f"{self.first_name} {self.last_name}"