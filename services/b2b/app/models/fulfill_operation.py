# app/models/fulfill_operation.py
from sqlalchemy import Column, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
from datetime import datetime, timezone
import uuid


class FulfillOperation(BaseModel):
    __tablename__ = "fulfill_operations"
    
    order_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    processed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc))
    
    # Relationships
    items = relationship("FulfillOperationItem", back_populates="operation", cascade="all, delete-orphan")


class FulfillOperationItem(BaseModel):
    __tablename__ = "fulfill_operation_items"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    operation_order_id = Column(GUID, ForeignKey("fulfill_operations.order_id"), nullable=False)
    sku_id = Column(GUID, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    
    # Relationships
    operation = relationship("FulfillOperation", back_populates="items")
    sku = relationship("SKU")