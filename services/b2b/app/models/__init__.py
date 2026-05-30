# app/models/__init__.py
from app.models.base import Base
from app.models.seller import Seller
from app.models.category import Category
from app.models.characteristic import Characteristic, CharacteristicValue, CategoryCharacteristic
from app.models.product import Product, ProductImage, ProductCharacteristic
from app.models.sku import SKU, SKUCharacteristic, SKUImage
from app.models.reservation import SKUReservation
from app.models.invoice import Invoice, InvoiceItem
from app.models.outbox import OutboxEvent
from app.models.history import ProductStatusHistory
from app.models.unreserve_operation import UnreserveOperation, UnreserveOperationItem  # ← добавить
from app.models.fulfill_operation import FulfillOperation, FulfillOperationItem  # ← добавить
from app.models.image import Image  # ← добавить


__all__ = [
    "Base",
    "Seller",
    "Category",
    "Characteristic",
    "CharacteristicValue",
    "CategoryCharacteristic",
    "Product",
    "ProductImage",
    "ProductCharacteristic",
    "SKU",
    "SKUCharacteristic",
    "SKUImage",
    "SKUReservation",
    "Invoice",
    "InvoiceItem",
    "OutboxEvent",
    "ProductStatusHistory",
    "UnreserveOperation",
    "UnreserveOperationItem",  # ← добавить
    "FulfillOperation",
    "FulfillOperationItem",    # ← добавить
    "Image",                   # ← добавить
]