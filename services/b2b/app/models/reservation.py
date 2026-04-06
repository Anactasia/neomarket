# app/models/reservation.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship  # ← добавить импорт
from sqlalchemy.sql import func
from app.models.base import BaseModel


class SKUReservation(BaseModel):
    """Резервирование товаров для заказов из B2C"""
    __tablename__ = "sku_reservations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(Integer, ForeignKey("skus.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(String(36), nullable=False)  # UUID из B2C
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), default="ACTIVE")  # ACTIVE, COMPLETED, CANCELLED, EXPIRED
    expires_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # ← добавить обратную связь
    sku = relationship("SKU", back_populates="reservations")