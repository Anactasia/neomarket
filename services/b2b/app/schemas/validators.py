# app/schemas/validators.py
"""
Централизованные валидаторы для B2B сервиса

Все правила валидации живут здесь.
При изменении требований (например, новый формат ИНН) -
достаточно поменять код в этом файле.
"""

import re
from typing import Optional


# ----- Seller validators -----
def validate_inn(inn: str) -> str:
    """ИНН: 10 или 12 цифр"""
    if not inn.isdigit():
        raise ValueError('ИНН должен содержать только цифры')
    if len(inn) not in [10, 12]:
        raise ValueError('ИНН должен быть 10 или 12 цифр')
    return inn


def validate_phone(phone: Optional[str]) -> Optional[str]:
    """Телефон: опционально, но если указан - проверяем формат"""
    if phone and not re.match(r'^\+?[0-9\s\-\(\)]{10,20}$', phone):
        raise ValueError('Неверный формат телефона')
    return phone


def validate_company_name(name: str) -> str:
    """Название компании: не пустое, не слишком длинное"""
    if len(name) < 2:
        raise ValueError('Название компании должно содержать минимум 2 символа')
    if len(name) > 255:
        raise ValueError('Название компании не может быть длиннее 255 символов')
    return name


# ----- Product validators -----
def validate_slug(slug: str) -> str:
    """Slug: только латиница, цифры, дефисы"""
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    if not re.match(pattern, slug):
        raise ValueError(
            'Slug может содержать только латинские буквы, цифры и дефисы. '
            'Пример: iphone-15-pro-max'
        )
    return slug


def validate_title(title: str) -> str:
    """Название товара: не пустое, не слишком длинное"""
    if len(title) < 3:
        raise ValueError('Название должно содержать минимум 3 символа')
    if len(title) > 500:
        raise ValueError('Название не может быть длиннее 500 символов')
    return title


# ----- SKU validators -----
def validate_price(price: int) -> int:
    """Цена: положительное число"""
    if price <= 0:
        raise ValueError('Цена должна быть больше 0')
    return price


def validate_quantity(quantity: int) -> int:
    """Количество: не отрицательное"""
    if quantity < 0:
        raise ValueError('Количество не может быть отрицательным')
    return quantity


def validate_compare_price(price: int, compare_price: Optional[int]) -> Optional[int]:
    """Сравнительная цена: если указана, должна быть больше текущей"""
    if compare_price is not None and compare_price <= price:
        raise ValueError('Старая цена должна быть больше текущей')
    return compare_price


def validate_sku_name(name: str) -> str:
    """Название SKU: не пустое"""
    if len(name) < 1:
        raise ValueError('Название SKU не может быть пустым')
    if len(name) > 500:
        raise ValueError('Название SKU не может быть длиннее 500 символов')
    return name