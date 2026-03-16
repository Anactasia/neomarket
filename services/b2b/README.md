

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
cd cd services/b2b
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



### Документация API
После запуска сервиса документация доступна по адресам:

Swagger UI: http://localhost:8000/api/docs


### 🛠 Основные эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/v1/sellers/` | Создать продавца |
| GET | `/api/v1/sellers/` | Список продавцов |
| POST | `/api/v1/categories/` | Создать категорию |
| GET | `/api/v1/categories/tree` | Дерево категорий |
| POST | `/api/v1/products/` | Создать товар |
| GET | `/api/v1/products/` | Список товаров |
| POST | `/api/v1/skus/` | Создать SKU |
| POST | `/api/v1/invoices/` | Создать накладную |
