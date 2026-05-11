# NeoMarket

## Быстрый запуск

```
cd services/b2b

docker-compose up -d --build

# 3. Импортировать категории
docker-compose exec b2b-service python scripts/import_categories.py

# 4. Проверить, что сервис работает
curl http://localhost:8000/health

# 5. Открыть Swagger UI
# http://localhost:8000/api/docs

```

## Запуск тестов
```
# Запустить только тесты US-B2B-01
docker-compose exec b2b-service pytest tests/test_us_b2b_01.py -v
```

## Ожидаемый результат тестов

```
=============================================== test session starts ================================================
collected 6 items                                                                                                  

tests/test_us_b2b_01.py::TestB2B01CreateProduct::test_create_product_returns_201_with_created_status PASSED  [ 16%]
tests/test_us_b2b_01.py::TestB2B01CreateProduct::test_seller_id_taken_from_jwt PASSED                        [ 33%]
tests/test_us_b2b_01.py::TestB2B01CreateProduct::test_missing_images_returns_400 PASSED                      [ 50%]
tests/test_us_b2b_01.py::TestB2B01CreateProduct::test_missing_category_returns_400 PASSED                    [ 66%]
tests/test_us_b2b_01.py::TestB2B01CreateProduct::test_invalid_category_id_returns_400 PASSED                 [ 83%]
tests/test_us_b2b_01.py::TestB2B01CreateProduct::test_title_too_long_returns_400 PASSED                      [100%]
```







## Структура микросервиса (шаблон)
```
b2b/
├── app/
│ ├── api/                  # Эндпоинты (products, auth, categories, skus, invoices)
│ ├── models/               # SQLAlchemy модели (seller, product, category, sku)
│ ├── schemas/              # Pydantic схемы (product, auth, common)
│ ├── core/                 # Общие утилиты 
│ └── dependencies/         # FastAPI зависимости (auth)
├── migrations/             # Alembic миграции БД
├── tests/                  # Pytest тесты
│ └── test_us_b2b_01.py         # Тесты US-B2B-01
├── scripts/                # Вспомогательные скрипты
│ └── import_categories.py      # Импорт категорий
├── data/                   # Статические данные
│ └── categories.json           # 115 категорий
├── Dockerfile              # Docker образ
├── docker-compose.yml      # Локальный запуск
├── requirements.txt        # Зависимости
└── README.md               # Документация
```




