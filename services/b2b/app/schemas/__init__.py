# app/schemas/__init__.py

# Auth (Seller)
from app.schemas.auth import (
    SellerCreate,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    SellerUpdate,
    SellerResponse,
)

# Category
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryWithChildrenResponse,  # ← добавить
    CategoryTreeResponse,
)

# Product
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductDetailResponse,  # ← добавить
    ProductStatus,
    ProductPublicResponse,
    ProductPublicShortResponse,
    ProductShortResponse,
    ProductPaginatedResponse,
    ProductPublicPaginatedResponse,
    ImageAttachRequest,
    ImageUpdateRequest,
    BatchProductIdsRequest,
)

# SKU
from app.schemas.sku import (
    SKUCreate,
    SKUUpdate,
    SKUResponse,
    SKUPublicResponse,
    # SKUInProduct — удален (не существует)
    SKUImageCreate,
    SKUImageResponse,
)

# Common (B2B)
from app.schemas.common import (
    CategoryRef,               
    Characteristic,           
    CharacteristicResponse,   
    Error,                    
    ProductImageCreate,       
    ProductImageResponse,     
    ImageEntityType,          
    ImageUploadResponse,
    PaginatedResponse      
)

# Invoice
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceAcceptRequest,
    InvoiceAcceptItem,
    InvoiceItemCreate,
    InvoiceItemResponse,
    InvoiceStatus,
    InvoicePaginatedResponse,
)

# Inventory
from app.schemas.reserve import (
    ReserveRequest,
    ReserveResponse,
    InventoryOrderRequest,
    InventoryOrderResponse,
)

# Moderation Events
from app.schemas.moderation import (
    ModerationEventRequest,
    ModerationEventType,
    FieldReport,  # ← добавить
    BlockingReason,  # ← добавить
)


__all__ = [
    # Auth
    "SellerCreate",
    "LoginRequest",
    "RefreshRequest",
    "TokenResponse",
    "SellerUpdate",
    "SellerResponse",
    
    # Category
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryResponse",
    "CategoryTreeResponse",
    "CategoryWithChildrenResponse",
    
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductDetailResponse",
    "ProductStatus",
    "ProductPublicResponse",
    "ProductPublicShortResponse",
    "ProductShortResponse",
    "ProductPaginatedResponse",
    "ProductPublicPaginatedResponse",
    "ImageAttachRequest",
    "ImageUpdateRequest",
    "BatchProductIdsRequest",
    
    # SKU
    "SKUCreate",
    "SKUUpdate",
    "SKUResponse",
    "SKUPublicResponse",
    "SKUImageCreate",
    "SKUImageResponse",
    
    # Common
    "Characteristic",
    "CharacteristicResponse",
    "ProductImageCreate",
    "PaginatedResponse",
    "ProductImageResponse",
    "ImageUploadResponse",
    "ImageEntityType"
    "Error",
    
    # Invoice
    "InvoiceCreate",
    "InvoiceResponse",
    "InvoiceAcceptRequest",
    "InvoiceAcceptItem",
    "InvoiceItemCreate",
    "InvoiceItemResponse",
    "InvoiceStatus",
    "InvoicePaginatedResponse",
    
    # Inventory
    "ReserveRequest",
    "ReserveResponse",
    "InventoryOrderRequest",
    "InventoryOrderResponse",
    
    # Moderation
    "ModerationEventRequest",
    "ModerationEventType",
    "FieldReport",
    "BlockingReason",
]