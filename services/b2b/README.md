

# NeoMarket B2B Service

Сервис для управления кабинетом продавца: товары, SKU, категории, характеристики и накладные.

## Требования
- Docker и Docker Compose
- Python 3.11+ (для локальной разработки)
- Git

##  Быстрый старт

### 1. Клонировать репозиторий
```bash
git clone <REPO_URL>
cd services/b2b
```
### 2. Запустить с помощью Docker (рекомендуется)
```bash
# Поднять базу данных и pgAdmin
docker-compose up -d postgres pgadmin

# Применить миграции
docker-compose run --rm b2b-service alembic upgrade head

# Запустить сервис
docker-compose up b2b-service
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
│   │   ├── products.py
│   │   ├── skus.py
│   │   ├── categories.py
│   │   ├── sellers.py
│   │   ├── invoices.py
│   │   ├── reserve.py
│   │   └── internal.py
│   ├── models/              # SQLAlchemy модели
│   │   ├── seller.py
│   │   ├── category.py
│   │   ├── product.py
│   │   ├── sku.py
│   │   ├── invoice.py
│   │   └── reservation.py
│   ├── schemas/             # Pydantic схемы
│   │   ├── common.py
│   │   ├── product.py
│   │   ├── sku.py
│   │   ├── category.py
│   │   ├── seller.py
│   │   ├── invoice.py
│   │   ├── reserve.py
│   │   └── moderation.py
│   ├── services/            # Бизнес-логика
│   ├── core/                # Утилиты
│   │   ├── database.py
│   │   └── config.py
│   └── main.py              # Точка входа
├── data/
│   └── categories.json      # 115 категорий Telegram-контента
├── scripts/
│   └── import_categories.py # Скрипт импорта категорий
├── migrations/              # Alembic миграции
├── tests/                   # Тесты
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```


# Тестирование

## Запуск всех тестов

```
docker-compose exec -e PYTHONPATH=/app b2b-service pytest tests/ -v
```

## Запуск всех тестов

```
# Тесты категорий
docker-compose exec -e PYTHONPATH=/app b2b-service pytest tests/test_categories.py -v

# Тесты продавцов
docker-compose exec -e PYTHONPATH=/app b2b-service pytest tests/test_sellers.py -v

# Тесты товаров
docker-compose exec -e PYTHONPATH=/app b2b-service pytest tests/test_products.py -v

# Тесты SKU
docker-compose exec -e PYTHONPATH=/app b2b-service pytest tests/test_skus.py -v

# Тесты накладных
docker-compose exec -e PYTHONPATH=/app b2b-service pytest tests/test_invoices.py -v
```

Проходят 30/32 теста. 2 теста не проходят по причине того, что тестовая БД SQLite (там нет UUID) потом исправлю


# Интеграция с другими сервисами

## Moderation Service
Отправка на модерацию: B2B отправляет товар при создании/изменении

Колбэк: Moderation вызывает POST /internal/moderation-callback с результатом

## B2C Service
Резервирование: B2C вызывает POST /reserve/ при оформлении заказа

Чтение товаров: B2C получает товары через GET /products/{id}

## Auth Service
Идентификация через заголовок X-User-Id (временно)