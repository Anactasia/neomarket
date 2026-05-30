# app/schemas/moderation.py

"""
Схемы для связи с Moderation сервисом
"""
from pydantic import BaseModel, Field  
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class ModerationEventType(str, Enum):
    MODERATED = "MODERATED"
    BLOCKED = "BLOCKED"


class FieldReport(BaseModel):
    """Замечание по конкретному полю товара или SKU"""
    field_name: str = Field(..., description='например "title", "description", "images[0]"')
    sku_id: Optional[UUID] = None
    comment: str


class ModerationEventRequest(BaseModel):
    """Событие от Moderation Service"""
    idempotency_key: UUID
    product_id: UUID
    event_type: ModerationEventType
    moderator_id: Optional[UUID] = None
    moderator_comment: Optional[str] = None
    blocking_reason_id: Optional[UUID] = None
    hard_block: bool = False
    field_reports: Optional[List[FieldReport]] = None
    occurred_at: datetime


class BlockingReason(BaseModel):
    """Причина блокировки (по спецификации B2B)"""
    id: UUID
    title: str
    comment: str = Field(..., description="Комментарий к причине блокировки")