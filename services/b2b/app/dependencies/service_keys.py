"""
Service-to-Service API Keys validation.
Раздельные ключи для разных каналов коммуникации.
"""
import os
from typing import Optional


def verify_b2c_service_key(x_service_key: Optional[str]) -> bool:
    """
    Проверяет валидность X-Service-Key для вызовов из B2C в B2B.
    
    Используется в public.py для публичного каталога.
    """
    expected_key = os.getenv("B2C_TO_B2B_KEY")
    if not expected_key:
        raise RuntimeError("B2C_TO_B2B_KEY environment variable is not set")
    return x_service_key == expected_key


def verify_moderation_service_key(x_service_key: Optional[str]) -> bool:
    """
    Проверяет валидность X-Service-Key для вызовов из Moderation в B2B.
    
    Используется в products.py для получения публичных карточек.
    """
    expected_key = os.getenv("B2B_TO_MOD_KEY")
    if not expected_key:
        raise RuntimeError("B2B_TO_MOD_KEY environment variable is not set")
    return x_service_key == expected_key


def verify_b2b_to_b2c_key(x_service_key: Optional[str]) -> bool:
    """
    Проверяет валидность X-Service-Key для вызовов из B2B в B2C.
    
    Используется в send_event_to_b2c_sync.
    """
    expected_key = os.getenv("B2B_TO_B2C_KEY", "b2b-to-b2c-key")
    return x_service_key == expected_key


# Deprecated — оставлен для обратной совместимости, но не использовать
def verify_service_key(x_service_key: Optional[str]) -> bool:
    """
    Устаревшая функция. Используйте специализированные функции:
    - verify_b2c_service_key() для B2C → B2B
    - verify_moderation_service_key() для Moderation → B2B
    """
    import warnings
    warnings.warn(
        "verify_service_key is deprecated. Use verify_b2c_service_key() or verify_moderation_service_key()",
        DeprecationWarning,
        stacklevel=2
    )
    expected_key = os.getenv("B2B_SERVICE_KEY", "b2b-service-key")
    return x_service_key == expected_key