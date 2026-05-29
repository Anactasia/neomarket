import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, func, CHAR
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import TypeDecorator

Base = declarative_base()

# Специальный костыль для тестов (SQLite + UUID)
class GUID(TypeDecorator):
    """Позволяет использовать UUID в Postgres и String в SQLite"""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value).hex
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


def now_utc():
    """Возвращает текущее UTC время"""
    return datetime.now(timezone.utc)


class BaseModel(Base):
    __abstract__ = True
    
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)