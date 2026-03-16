from enum import Enum


class ProductStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_MODERATION = "PENDING_MODERATION"
    ON_MODERATION = "ON_MODERATION"
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"
    ARCHIVED = "ARCHIVED"


class InvoiceStatus(str, Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SellerStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"