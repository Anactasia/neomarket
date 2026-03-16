# app/models/base.py
from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import declarative_base
import uuid

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())