from sqlalchemy import Column, DateTime
from app.models.base import BaseModel, GUID
from datetime import datetime, timezone
import uuid

class UnreserveOperation(BaseModel):
    __tablename__ = "unreserve_operations"
    
    order_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    processed_at = Column(DateTime(timezone=True), nullable=False)