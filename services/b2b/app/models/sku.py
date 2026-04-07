# app/models/sku.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DECIMAL, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel, GUID
import uuid

# Для type hints (опционально, но рекомендуется)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.reservation import SKUReservation


class SKU(BaseModel):
    __tablename__ = "skus"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    product_id = Column(GUID, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    seller_sku = Column(String(100))
    barcode = Column(String(100))
    name = Column(String(500), nullable=False)
    
    price = Column(Integer, nullable=False)
    compare_at_price = Column(Integer)
    quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    main_image_id = Column(GUID, ForeignKey("product_images.id"), nullable=True)
    
    # Relationships
    product = relationship("Product", back_populates="skus")
    main_image = relationship("ProductImage")
    characteristics = relationship("SKUCharacteristic", back_populates="sku", cascade="all, delete-orphan")
    reservations = relationship("SKUReservation", back_populates="sku", cascade="all, delete-orphan")  # ← строка остаётся

class SKUCharacteristic(BaseModel):
    __tablename__ = "sku_characteristics"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    sku_id = Column(GUID, ForeignKey("skus.id", ondelete="CASCADE"))
    characteristic_id = Column(GUID, ForeignKey("characteristics.id", ondelete="CASCADE"))
    
    value_string = Column(Text)
    value_int = Column(Integer)
    value_float = Column(DECIMAL(10, 2))
    value_bool = Column(Boolean)
    characteristic_value_id = Column(GUID, ForeignKey("characteristic_values.id"))
    
    # Relationships
    sku = relationship("SKU", back_populates="characteristics")
    characteristic = relationship("Characteristic", foreign_keys=[characteristic_id])
    enum_value = relationship("CharacteristicValue", foreign_keys=[characteristic_value_id])