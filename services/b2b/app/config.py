import os
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

class Settings:
    # Database settings
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "neomarket_b2b")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASS: str = os.getenv("DB_PASS", "postgres")
    
    # JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-minimum-32-characters")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 часа
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))  # 7 дней
    
    # Service-to-Service API Keys
    B2C_TO_B2B_KEY: str = os.getenv("B2C_TO_B2B_KEY")  # ключ для вызовов из B2C в B2B
    B2B_TO_MOD_KEY: str = os.getenv("B2B_TO_MOD_KEY")  # ключ для вызовов из B2B в Moderation
    B2B_TO_B2C_KEY: str = os.getenv("B2B_TO_B2C_KEY", "b2b-to-b2c-key")  # ← добавить: ключ для вызовов из B2B в B2C
    
    # Service URLs
    B2C_SERVICE_URL: str = os.getenv("B2C_SERVICE_URL", "http://b2c:8000/api/v1/b2b/events")  # ← добавить
    MODERATION_SERVICE_URL: str = os.getenv("MODERATION_SERVICE_URL", "http://moderation:8000")  # ← добавить
    
    @property
    def DATABASE_URL(self) -> str:
        """Формируем URL для подключения"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    def validate_service_keys(self) -> None:
        """Проверяет, что все обязательные сервисные ключи заданы"""
        if not self.B2C_TO_B2B_KEY:
            raise ValueError("B2C_TO_B2B_KEY environment variable is required")
        if not self.B2B_TO_MOD_KEY:
            raise ValueError("B2B_TO_MOD_KEY environment variable is required")
        # B2B_TO_B2C_KEY не обязательный, есть дефолт


settings = Settings()

# Валидируем ключи при старте приложения (вызвать в main.py)
# settings.validate_service_keys()