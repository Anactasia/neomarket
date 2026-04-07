# app/models/characteristic.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DECIMAL, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid

class CategoryCharacteristic(BaseModel):
    __tablename__ = "category_characteristics"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    category_id = Column(GUID, ForeignKey("categories.id", ondelete="CASCADE"))
    characteristic_id = Column(GUID, ForeignKey("characteristics.id", ondelete="CASCADE"))
    is_filter = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    
    category = relationship("Category", back_populates="characteristics")
    characteristic = relationship("Characteristic", back_populates="categories")

class Characteristic(BaseModel):
    __tablename__ = "characteristics"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    type = Column(String(20), nullable=False)  # 'string', 'integer', 'float', 'boolean'
    is_global = Column(Boolean, default=True)
    
    
    categories = relationship("CategoryCharacteristic", back_populates="characteristic")
    values = relationship("CharacteristicValue", back_populates="characteristic")

class CharacteristicValue(BaseModel):
    __tablename__ = "characteristic_values"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    characteristic_id = Column(GUID, ForeignKey("characteristics.id", ondelete="CASCADE"))
    value = Column(String(255), nullable=False)
    
    
    characteristic = relationship("Characteristic", back_populates="values")