

# NeoMarket B2B Service

Сервис для управления кабинетом продавца: товары, SKU, категории, характеристики и накладные.

## Требования
- Docker и Docker Compose
- Python 3.11+ (для локальной разработки)
- Git

##  Быстрый старт

### 1. Клонировать репозиторий
```bash
# 1. Клонировать репозиторий
git clone <REPO_URL>
cd services/b2b

# 2. Запустить сервис (миграции применяются автоматически)
docker-compose up -d --build

# 3. Импортировать категории
docker-compose exec b2b-service python scripts/import_categories.py
```


### Переменные окружения
Создай файл .env в корне сервиса:
Скопируй файл .env.example в .env и отредактируй при необходимости

### 3. Импорт категорий

```
# Импортировать 115 категорий Telegram-контента
docker-compose exec b2b-service python scripts/import_categories.py --clear
```

### Документация API
После запуска сервиса документация доступна по адресам:

Swagger UI: http://localhost:8000/api/docs


## 🛠 Основные эндпоинты

### Аутентификация (Auth)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/auth/register` | Регистрация продавца |
| POST | `/api/auth/login` | Логин (получение JWT) |
| POST | `/api/auth/refresh` | Обновление токена |
| POST | `/api/auth/logout` | Выход |

### Продавцы (Sellers)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/sellers/` | Создать продавца |
| GET | `/api/v1/sellers/` | Список продавцов |
| GET | `/api/v1/sellers/{id}` | Получить продавца по ID |
| PUT | `/api/v1/sellers/{id}` | Обновить данные продавца |

### Категории (Categories)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/v1/categories/` | Список категорий |
| GET | `/api/v1/categories/tree` | Дерево категорий |
| GET | `/api/v1/categories/{id}` | Получить категорию по ID |

> **Примечание:** Категории доступны только для чтения. Создание и редактирование категорий выполняет техподдержка через админ-панель.

### Товары (Products)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/products/` | Создать товар |
| GET | `/api/v1/products/` | Список товаров продавца |
| GET | `/api/v1/products/{id}` | Получить товар с SKU |
| PUT | `/api/v1/products/{id}` | Обновить товар |
| DELETE | `/api/v1/products/{id}` | Удалить товар |

### SKU (Варианты товаров)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/skus/` | Создать SKU |
| GET | `/api/v1/skus/` | Список SKU |
| GET | `/api/v1/skus/{id}` | Получить SKU по ID |
| PUT | `/api/v1/skus/{id}` | Обновить SKU |
| PUT | `/api/v1/skus/{id}/quantity` | Обновить остаток SKU |
| DELETE | `/api/v1/skus/{id}` | Удалить SKU |

### Накладные (Invoices)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/invoices/` | Создать накладную |
| GET | `/api/v1/invoices/` | Список накладных |
| GET | `/api/v1/invoices/{id}` | Получить накладную по ID |
| POST | `/api/v1/invoices/{id}/accept` | Принять накладную |

### Интеграционные эндпоинты

| Метод | Путь | Описание | Вызывается |
|-------|------|----------|------------|
| POST | `/api/v1/reserve/` | Зарезервировать товары | B2C сервис |
| POST | `/api/v1/internal/moderation-callback` | Получить результат модерации | Moderation сервис |




## Статусы товара
```
CREATED → ON_MODERATION → MODERATED (опубликован)
                    ↘ BLOCKED (заблокирован)
```
CREATED — товар создан, ожидает отправки на модерацию

ON_MODERATION — на проверке у модератора

MODERATED — одобрен, виден покупателям

BLOCKED — заблокирован, продавец видит причину



## Структура проекта(примерно)

```
b2b/
├── app/
│   ├── api/                 # Эндпоинты
│   │   ├── auth.py          # JWT аутентификация
│   │   ├── products.py      # CRUD товаров
│   │   ├── categories.py    # Категории
│   │   ├── skus.py          # SKU
│   │   └── invoices.py      # Накладные
│   ├── models/              # SQLAlchemy модели
│   │   ├── seller.py
│   │   ├── product.py
│   │   ├── category.py
│   │   └── sku.py
│   ├── schemas/             # Pydantic схемы
│   │   ├── common.py        # Общие схемы (CategoryRef, Image, CharacteristicValue)
│   │   ├── product.py       # ProductCreate, ProductResponse
│   │   └── auth.py          # Регистрация, логин
│   ├── core/                # Утилиты
│   │   ├── database.py
│   │   ├── config.py
│   │   └── security.py      # JWT, хеширование
│   ├── dependencies/        # FastAPI зависимости
│   │   └── auth.py          # get_current_seller
│   └── main.py              # Точка входа
├── migrations/              # Alembic миграции
├── tests/
│   └── test_us_b2b_01.py    # Тесты создания товара
├── scripts/
│   └── import_categories.py # Импорт категорий
├── data/
│   └── categories.json      # 115 категорий
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```


