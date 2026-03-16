# app/config.py
import os
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

class Settings:
    # Берем из переменных окружения, если нет - используем значения по умолчанию
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "neomarket_b2b")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASS: str = os.getenv("DB_PASS", "postgres")
    
    @property
    def DATABASE_URL(self) -> str:
        """Формируем URL для подключения"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()