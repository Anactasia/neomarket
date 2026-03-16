# app/models/characteristic.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DECIMAL, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class CategoryCharacteristic(BaseModel):
    __tablename__ = "category_characteristics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"))
    characteristic_id = Column(Integer, ForeignKey("characteristics.id", ondelete="CASCADE"))
    is_filter = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    
    category = relationship("Category", back_populates="characteristics")
    characteristic = relationship("Characteristic", back_populates="categories")

class Characteristic(BaseModel):
    __tablename__ = "characteristics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    type = Column(String(20), nullable=False)  # 'string', 'integer', 'float', 'boolean'
    is_global = Column(Boolean, default=True)
    
    
    categories = relationship("CategoryCharacteristic", back_populates="characteristic")
    values = relationship("CharacteristicValue", back_populates="characteristic")

class CharacteristicValue(BaseModel):
    __tablename__ = "characteristic_values"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    characteristic_id = Column(Integer, ForeignKey("characteristics.id", ondelete="CASCADE"))
    value = Column(String(255), nullable=False)
    
    
    characteristic = relationship("Characteristic", back_populates="values")