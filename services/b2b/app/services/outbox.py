from sqlalchemy.orm import Session
from app.models.outbox import OutboxEvent
from uuid import UUID
from typing import Optional, Dict, Any

def save_to_outbox(
    db: Session,
    event_type: str,
    target: str,
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None
) -> OutboxEvent:
    """Сохраняет событие в outbox для последующей отправки"""
    
    print(f"DEBUG save_to_outbox: event_type={event_type}, target={target}")  # ← ДОБАВИТЬ
    
    outbox_event = OutboxEvent(
        event_type=event_type,
        target=target,
        url=url,
        payload=payload,
        headers=headers,
        status="PENDING"
    )
    db.add(outbox_event)
    print(f"DEBUG save_to_outbox: outbox_event добавлен, id={outbox_event.id}")  # ← ДОБАВИТЬ
    
    db.flush()
    print(f"DEBUG save_to_outbox: flush выполнен")  # ← ДОБАВИТЬ
    
    # Проверим, что запись действительно в сессии
    existing = db.query(OutboxEvent).filter(OutboxEvent.id == outbox_event.id).first()
    print(f"DEBUG save_to_outbox: запись в БД после flush: {existing is not None}")  # ← ДОБАВИТЬ
    
    return outbox_event