# app/models/fulfill_operation.py
from sqlalchemy import Column, DateTime
from app.models.base import BaseModel, GUID
from datetime import datetime, timezone
import uuid

class FulfillOperation(BaseModel):
    __tablename__ = "fulfill_operations"
    
    order_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    processed_at = Column(DateTime(timezone=True), nullable=False)