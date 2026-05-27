from sqlalchemy import Column, String, DateTime, JSON, Integer
from sqlalchemy.sql import func
from app.models.base import BaseModel, GUID
import uuid

class OutboxEvent(BaseModel):
    __tablename__ = "outbox_events"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)  # PRODUCT_CREATED, PRODUCT_EDITED, PRODUCT_DELETED, SKU_OUT_OF_STOCK
    target = Column(String(20), nullable=False)  # moderation, b2c
    payload = Column(JSON, nullable=False)
    headers = Column(JSON, nullable=True)  # X-Service-Key и другие заголовки
    url = Column(String(500), nullable=False)  # полный URL для запроса
    status = Column(String(20), default="PENDING")  # PENDING, SENT, FAILED
    retry_count = Column(Integer, default=0)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<OutboxEvent {self.id} {self.event_type} {self.status}>"