# app/models/unreserve_operation.py
from sqlalchemy import Column, DateTime, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
from datetime import datetime, timezone
import uuid


class UnreserveOperation(BaseModel):
    __tablename__ = "unreserve_operations"
    
    order_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    processed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('ix_unreserve_operations_processed_at', 'processed_at'),
    )
    
    # Relationships
    items = relationship("UnreserveOperationItem", back_populates="operation", cascade="all, delete-orphan")


class UnreserveOperationItem(BaseModel):
    __tablename__ = "unreserve_operation_items"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    operation_order_id = Column(GUID, ForeignKey("unreserve_operations.order_id"), nullable=False)
    sku_id = Column(GUID, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    
    __table_args__ = (
        Index('ix_unreserve_operation_items_operation_order_id', 'operation_order_id'),
        Index('ix_unreserve_operation_items_sku_id', 'sku_id'),
    )
    
    # Relationships
    operation = relationship("UnreserveOperation", back_populates="items")
    sku = relationship("SKU")