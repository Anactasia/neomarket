# app/schemas/moderation.py

"""
Схемы для связи с Moderation сервисом
"""
from pydantic import BaseModel, Field  
from typing import Optional
from uuid import UUID


class ModerationCallback(BaseModel):
    """Колбэк от Moderation сервиса"""
    product_id: UUID
    decision: str  # APPROVED, DECLINED
    blocking_reason_id: Optional[int] = None
    comment: Optional[str] = Field(None, max_length=1000)