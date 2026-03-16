# app/schemas/characteristic.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CharacteristicBase(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    type: str = Field(..., pattern="^(string|integer|float|boolean)$")
    is_global: bool = True

class CharacteristicCreate(CharacteristicBase):
    pass

class Characteristic(CharacteristicBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True