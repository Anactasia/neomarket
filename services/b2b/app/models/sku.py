# app/models/sku.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DECIMAL, DateTime, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class SKU(BaseModel):
    __tablename__ = "skus"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    
    seller_sku = Column(String(100))
    barcode = Column(String(100))
    name = Column(String(500), nullable=False)
    
    price = Column(Integer, nullable=False)
    compare_at_price = Column(Integer)
    quantity = Column(Integer, nullable=False, default=0)
    
    is_active = Column(Boolean, default=True)
    main_image_id = Column(Integer, ForeignKey("product_images.id"), nullable=True)
    
    product = relationship("Product", back_populates="skus")
    main_image = relationship("ProductImage")
    characteristics = relationship("SKUCharacteristic", back_populates="sku", cascade="all, delete-orphan")
    reservations = relationship("SKUReservation", back_populates="sku", cascade="all, delete-orphan")

class SKUCharacteristic(BaseModel):
    __tablename__ = "sku_characteristics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(Integer, ForeignKey("skus.id", ondelete="CASCADE"))
    characteristic_id = Column(Integer, ForeignKey("characteristics.id", ondelete="CASCADE"))
    
    value_string = Column(Text)
    value_int = Column(Integer)
    value_float = Column(DECIMAL(10, 2))
    value_bool = Column(Boolean)
    characteristic_value_id = Column(Integer, ForeignKey("characteristic_values.id"))
    
    sku = relationship("SKU", back_populates="characteristics")
    characteristic = relationship("Characteristic", foreign_keys=[characteristic_id])
    enum_value = relationship("CharacteristicValue", foreign_keys=[characteristic_value_id])

class SKUReservation(BaseModel):
    __tablename__ = "sku_reservations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(Integer, ForeignKey("skus.id", ondelete="CASCADE"))
    order_id = Column(String(36), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), default="ACTIVE")  # ACTIVE, COMPLETED, CANCELLED, EXPIRED
    expires_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    sku = relationship("SKU", back_populates="reservations")