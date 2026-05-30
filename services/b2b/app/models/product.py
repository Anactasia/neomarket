# app/models/product.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime, DECIMAL, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON
from app.models.base import BaseModel, GUID
import uuid


class Product(BaseModel):
    __tablename__ = "products"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    seller_id = Column(GUID, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(GUID, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    slug = Column(String(500), nullable=True)
    description = Column(Text)
    
    main_image_id = Column(
        GUID,
        ForeignKey("product_images.id", use_alter=True, name="fk_product_main_image"),
        nullable=True
    )
    
    status = Column(String(20), nullable=False, default="CREATED")
    moderation_comment = Column(Text)
    blocking_reason_id = Column(GUID, nullable=True)
    field_reports_json = Column(JSON, default=list)
    
    published_at = Column(DateTime(timezone=True), nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)
    blocked = Column(Boolean, default=False, nullable=False)
    
    characteristics_json = Column(JSON, default=list)
    
    # Индексы
    __table_args__ = (
        Index('ix_products_seller_id', 'seller_id'),
        Index('ix_products_category_id', 'category_id'),
        Index('ix_products_status', 'status'),
        Index('ix_products_deleted', 'deleted'),
        Index('ix_products_created_at', 'created_at'),
        Index('ix_products_slug', 'slug'),
    )
    
    # Relationships
    seller = relationship("Seller", back_populates="products")
    category = relationship("Category", back_populates="products")
    skus = relationship("SKU", back_populates="product", cascade="all, delete-orphan")
    
    # Исправлено: явно указан foreign_keys
    images = relationship(
        "ProductImage", 
        back_populates="product", 
        cascade="all, delete-orphan",
        foreign_keys="ProductImage.product_id"
    )
    
    characteristics = relationship("ProductCharacteristic", back_populates="product", cascade="all, delete-orphan")
    
    # Для main_image тоже нужно указать foreign_keys
    main_image = relationship(
        "ProductImage", 
        foreign_keys=[main_image_id]
    )
    
    status_history = relationship("ProductStatusHistory", back_populates="product", cascade="all, delete-orphan")


class ProductImage(BaseModel):
    __tablename__ = "product_images"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    product_id = Column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500))
    sort_order = Column(Integer, default=0)
    is_main = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('ix_product_images_product_id', 'product_id'),
        Index('ix_product_images_sort_order', 'sort_order'),
        Index('ix_product_images_is_main', 'is_main'),
    )
    
    product = relationship(
        "Product", 
        back_populates="images",
        foreign_keys=[product_id]  # ← явно указываем foreign_key
    )


class ProductCharacteristic(BaseModel):
    __tablename__ = "product_characteristics"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    product_id = Column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    characteristic_id = Column(GUID, ForeignKey("characteristics.id", ondelete="CASCADE"))
    
    value_string = Column(Text)
    value_int = Column(Integer)
    value_float = Column(DECIMAL(10, 2))
    value_bool = Column(Boolean)
    characteristic_value_id = Column(GUID, ForeignKey("characteristic_values.id"))
    
    __table_args__ = (
        Index('ix_product_characteristics_product_id', 'product_id'),
        Index('ix_product_characteristics_characteristic_id', 'characteristic_id'),
    )
    
    product = relationship("Product", back_populates="characteristics")
    characteristic = relationship("Characteristic", foreign_keys=[characteristic_id])
    enum_value = relationship("CharacteristicValue", foreign_keys=[characteristic_value_id])