# app/services/outbox_worker.py
import logging
import asyncio
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional

from app.models.outbox import OutboxEvent
from app.database import SessionLocal

logger = logging.getLogger(__name__)


class OutboxWorker:
    """Воркер для отправки событий из outbox"""
    
    def __init__(
        self,
        batch_size: int = 100,
        poll_interval: float = 5.0,
        max_retries: int = 3
    ):
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запуск воркера"""
        if self._running:
            logger.warning("OutboxWorker already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("OutboxWorker started")
    
    async def stop(self):
        """Остановка воркера"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OutboxWorker stopped")
    
    async def _run(self):
        """Основной цикл воркера"""
        while self._running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.exception(f"Error processing outbox batch: {e}")
            await asyncio.sleep(self.poll_interval)
    
    async def _process_batch(self):
        """Обработка одной пачки событий"""
        db = SessionLocal()
        try:
            # Берём события со статусом PENDING
            events = db.query(OutboxEvent).filter(
                OutboxEvent.status == "PENDING"
            ).order_by(
                OutboxEvent.created_at
            ).limit(self.batch_size).all()
            
            if not events:
                return
            
            logger.info(f"Processing {len(events)} outbox events")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                for event in events:
                    await self._send_event(client, db, event)
            
            db.commit()
        finally:
            db.close()
    
    async def _send_event(self, client: httpx.AsyncClient, db: Session, event: OutboxEvent):
        """Отправка одного события"""
        try:
            logger.debug(f"Sending event {event.id}: {event.event_type} to {event.target}")
            
            response = await client.post(
                event.url,
                json=event.payload,
                headers=event.headers or {}
            )
            
            if response.status_code in [200, 201, 202, 204]:
                # Успешно
                event.status = "SENT"
                event.processed_at = datetime.now(timezone.utc)
                event.error_message = None
                logger.info(f"Event {event.id} sent successfully to {event.target}")
            else:
                # Ошибка HTTP
                event.retry_count += 1
                event.error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                if event.retry_count >= self.max_retries:
                    event.status = "FAILED"
                    logger.error(f"Event {event.id} failed after {self.max_retries} retries: {event.error_message}")
                else:
                    logger.warning(f"Event {event.id} failed (retry {event.retry_count}/{self.max_retries}): {event.error_message}")
        
        except httpx.TimeoutException as e:
            event.retry_count += 1
            event.error_message = f"Timeout: {str(e)}"
            if event.retry_count >= self.max_retries:
                event.status = "FAILED"
            logger.warning(f"Event {event.id} timeout (retry {event.retry_count}/{self.max_retries})")
        
        except Exception as e:
            event.retry_count += 1
            event.error_message = str(e)
            if event.retry_count >= self.max_retries:
                event.status = "FAILED"
            logger.exception(f"Event {event.id} error: {e}")
        
        db.flush()


# Глобальный экземпляр воркера
_worker: Optional[OutboxWorker] = None


def get_worker() -> OutboxWorker:
    """Получить глобальный экземпляр воркера"""
    global _worker
    if _worker is None:
        _worker = OutboxWorker()
    return _worker