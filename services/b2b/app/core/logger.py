# app/core/logger.py
import logging
import sys

def setup_logging():
    """Настройка логирования для приложения"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Отдельный логгер для SQLAlchemy (опционально)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)