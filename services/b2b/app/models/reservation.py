# app/models/reservation.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import BaseModel, GUID
from enum import Enum
import uuid


class ReservationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class SKUReservation(BaseModel):
    """Резервирование товаров для заказов из B2C"""
    __tablename__ = "sku_reservations"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    sku_id = Column(GUID, ForeignKey("skus.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(GUID, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), default=ReservationStatus.ACTIVE.value)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # created_at и updated_at — из BaseModel, не переопределяем!
    
    # Индексы
    __table_args__ = (
        Index('ix_sku_reservations_sku_id', 'sku_id'),
        Index('ix_sku_reservations_order_id', 'order_id'),
        Index('ix_sku_reservations_status', 'status'),
        Index('ix_sku_reservations_expires_at', 'expires_at'),
        Index('ix_sku_reservations_status_expires_at', 'status', 'expires_at'),
    )
    
    # Relationships
    sku = relationship("SKU", back_populates="reservations")