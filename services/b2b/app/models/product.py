# app/models/product.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime, DECIMAL
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Product(BaseModel):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(String(36), ForeignKey("sellers.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    
    title = Column(String(500), nullable=False)
    description = Column(Text)
    slug = Column(String(500), unique=True, nullable=False)
    
    main_image_id = Column(Integer, ForeignKey("product_images.id"), nullable=True)
    
    # SEO
    meta_title = Column(String(500))
    meta_description = Column(Text)
    meta_keywords = Column(Text)
    
    status = Column(String(20), nullable=False, default="DRAFT")
    moderation_comment = Column(Text)
    
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    seller = relationship("Seller", back_populates="products")
    category = relationship("Category", back_populates="products")
    skus = relationship("SKU", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan", foreign_keys="ProductImage.product_id")
    characteristics = relationship("ProductCharacteristic", back_populates="product", cascade="all, delete-orphan")
    main_image = relationship("ProductImage", foreign_keys=[main_image_id])

class ProductImage(BaseModel):
    __tablename__ = "product_images"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500))
    sort_order = Column(Integer, default=0)
    is_main = Column(Boolean, default=False)
    
    product = relationship("Product", back_populates="images", foreign_keys=[product_id])

class ProductCharacteristic(BaseModel):
    __tablename__ = "product_characteristics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    characteristic_id = Column(Integer, ForeignKey("characteristics.id", ondelete="CASCADE"))
    
    value_string = Column(Text)
    value_int = Column(Integer)
    value_float = Column(DECIMAL(10, 2))
    value_bool = Column(Boolean)
    characteristic_value_id = Column(Integer, ForeignKey("characteristic_values.id"))
    
    product = relationship("Product", back_populates="characteristics")
    characteristic = relationship("Characteristic", foreign_keys=[characteristic_id])
    enum_value = relationship("CharacteristicValue", foreign_keys=[characteristic_value_id])