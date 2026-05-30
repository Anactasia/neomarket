# app/models/category.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text, Index
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
    path = Column(String(1000), nullable=True)  # ← добавлено для materialized path
    image_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    is_restricted = Column(Boolean, default=False)
    
    # Индексы
    __table_args__ = (
        Index('ix_categories_parent_id', 'parent_id'),
        Index('ix_categories_path', 'path'),
        Index('ix_categories_is_active', 'is_active'),
    )
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("Product", back_populates="category")
    characteristics = relationship(
        "CategoryCharacteristic",
        back_populates="category",
        cascade="all, delete-orphan"
    )