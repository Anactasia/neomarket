# app/schemas/__init__.py

# Auth
from app.schemas.seller import (
    SellerRegisterRequest,
    SellerLoginRequest,
    RefreshRequest,
    TokenResponse,
    SellerUpdateRequest,
    SellerResponse,
)

# Category
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryTreeResponse,
)

# Product
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductStatus,
    ProductPublicResponse,
    ProductPublicShortResponse,
    ProductShortResponse,
    ProductPaginatedResponse,
    ProductPublicPaginatedResponse,
    FieldReport,
    BlockingReason,
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
    SKUInProduct,
    SKUImageCreate,
    SKUImageResponse,
)

# Characteristic (по спецификации B2B)
from app.schemas.common import (
    CharacteristicValue,
    CharacteristicValueResponse,
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

# Inventory (reserve/unreserve/fulfill)
from app.schemas.reserve import (
    ReserveRequest,
    ReserveSuccessResponse,
    ReserveErrorResponse,
    UnreserveRequest,
    UnreserveSuccessResponse,
    InventoryOrderRequest,
    InventoryOrderResponse,
)

# Moderation Events
from app.schemas.moderation import (
    ModerationEventRequest,
    ModerationEventType,
)

# Common
from app.schemas.common import (
    CategoryRef,
    Error,
    Pagination,
    ProductImageCreate,
    ProductImageResponse,
    ImageUploadResponse,
)


__all__ = [
    # Auth
    "SellerRegisterRequest",
    "SellerLoginRequest",
    "RefreshRequest",
    "TokenResponse",
    "SellerUpdateRequest",
    "SellerResponse",
    
    # Category
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryResponse",
    "CategoryTreeResponse",
    
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductStatus",
    "ProductPublicResponse",
    "ProductPublicShortResponse",
    "ProductShortResponse",
    "ProductPaginatedResponse",
    "ProductPublicPaginatedResponse",
    "FieldReport",
    "BlockingReason",
    "ImageAttachRequest",
    "ImageUpdateRequest",
    "BatchProductIdsRequest",
    
    # SKU
    "SKUCreate",
    "SKUUpdate",
    "SKUResponse",
    "SKUPublicResponse",
    "SKUInProduct",
    "SKUImageCreate",
    "SKUImageResponse",
    
    # Characteristic
    "CharacteristicValue",
    "CharacteristicValueResponse",
    
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
    "ReserveSuccessResponse",
    "ReserveErrorResponse",
    "UnreserveRequest",
    "UnreserveSuccessResponse",
    "InventoryOrderRequest",
    "InventoryOrderResponse",
    
    # Moderation
    "ModerationEventRequest",
    "ModerationEventType",
    
    # Common
    "CategoryRef",
    "Error",
    "Pagination",
    "ProductImageCreate",
    "ProductImageResponse",
    "ImageUploadResponse",
]