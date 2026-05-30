# app/models/image.py
from sqlalchemy import Column, String, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid


class Image(BaseModel):
    __tablename__ = "images"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    url = Column(String(500), nullable=False)
    ordering = Column(Integer, default=0)
    entity_type = Column(String(20), nullable=False)  # "PRODUCT" или "SKU"
    entity_id = Column(GUID, nullable=True)  # может быть NULL для неподшитых
    
    # Индексы
    __table_args__ = (
        Index('ix_images_entity_type_entity_id', 'entity_type', 'entity_id'),
        Index('ix_images_entity_id', 'entity_id'),
        Index('ix_images_entity_type', 'entity_type'),
    )
    
    # Опциональные связи (только для чтения, без каскадов)
    # product = relationship("Product", foreign_keys=[entity_id], viewonly=True)
    # sku = relationship("SKU", foreign_keys=[entity_id], viewonly=True)
    
    def __repr__(self):
        return f"<Image {self.id} ({self.entity_type})>"