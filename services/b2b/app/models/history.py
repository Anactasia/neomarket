# app/models/history.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid


class ProductStatusHistory(BaseModel):
    __tablename__ = "product_status_history"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    product_id = Column(GUID, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20), nullable=False)
    changed_by = Column(GUID, nullable=True)  # ← UUID (ID модератора или продавца)
    reason = Column(Text)
    comment = Column(Text)
    
    # Индексы
    __table_args__ = (
        Index('ix_product_status_history_product_id', 'product_id'),
        Index('ix_product_status_history_new_status', 'new_status'),
        Index('ix_product_status_history_created_at', 'created_at'),
        Index('ix_product_status_history_changed_by', 'changed_by'),
    )
    
    # Relationships
    product = relationship("Product", back_populates="status_history")
    # Опционально: связь с Seller (если changed_by ссылается на продавца/модератора)
    # changed_by_seller = relationship("Seller", foreign_keys=[changed_by])