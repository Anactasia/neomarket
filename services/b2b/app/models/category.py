# app/models/category.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid

class Category(BaseModel):
    __tablename__ = "categories"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    parent_id = Column(GUID, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)
    level = Column(Integer, default=0)
    image_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    is_restricted = Column(Boolean, default=False)  # (для 18+ контента)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("Product", back_populates="category")
    characteristics = relationship(
        "CategoryCharacteristic",
        back_populates="category",
        cascade="all, delete-orphan"
    )