# app/models/characteristic.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DECIMAL, Text, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid
from enum import Enum


class CharacteristicType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


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
    
    # Индексы
    __table_args__ = (
        Index('ix_characteristics_type', 'type'),
        Index('ix_characteristics_is_global', 'is_global'),
    )
    
    # Relationships
    categories = relationship("CategoryCharacteristic", back_populates="characteristic")
    values = relationship("CharacteristicValue", back_populates="characteristic")
    
    # Связи с товарами и SKU
    product_characteristics = relationship("ProductCharacteristic", back_populates="characteristic")
    sku_characteristics = relationship("SKUCharacteristic", back_populates="characteristic")


class CharacteristicValue(BaseModel):
    __tablename__ = "characteristic_values"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    characteristic_id = Column(GUID, ForeignKey("characteristics.id", ondelete="CASCADE"))
    value = Column(String(255), nullable=False)
    
    characteristic = relationship("Characteristic", back_populates="values")
    
    # Связи с товарами/SKU, использующими это значение
    product_characteristics = relationship("ProductCharacteristic", back_populates="enum_value")
    sku_characteristics = relationship("SKUCharacteristic", back_populates="enum_value")