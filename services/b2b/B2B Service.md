📁 NeoMarket B2B Service

📋 Описание проекта

Сервис для управления кабинетом продавца: товары, SKU, категории, характеристики и накладные.

🗂 Полная структура проекта

text

b2b-service/

├── app/

│   ├── \_\_init\_\_.py

│   ├── main.py                 # FastAPI приложение

│   ├── config.py                # Настройки и конфигурация

│   ├── database.py              # Подключение к БД

│   │

│   ├── models/                  # SQLAlchemy модели

│   │   ├── \_\_init\_\_.py

│   │   ├── base.py              # BaseModel с created\_at/updated\_at

│   │   ├── seller.py            # Модель продавца

│   │   ├── category.py          # Категории товаров

│   │   ├── product.py           # Товары и их изображения

│   │   ├── sku.py               # Варианты товаров (SKU)

│   │   ├── characteristic.py    # Характеристики

│   │   ├── invoice.py           # Накладные

│   │   └── history.py           # История статусов

│   │

│   ├── schemas/                  # Pydantic модели (пусто)

│   ├── api/                      # Роутеры (пусто)

│   ├── services/                 # Бизнес-логика (пусто)

│   └── core/                     # Утилиты (пусто)

│

├── migrations/                    # Alembic миграции

│   ├── versions/                  # Файлы миграций

│   ├── env.py                     # Конфигурация Alembic

│   └── script.py.mako             # Шаблон для миграций

│

├── tests/                          # Тесты (пусто)

├── alembic.ini                     # Конфиг Alembic

├── .env                            # Переменные окружения

├── requirements.txt                # Зависимости

├── docker-compose.yml              # Docker конфиг

├── Dockerfile                      # Docker образ

├── test\_connection.py              # Тест подключения к БД

└── README.md                       # Документация

📦 Модели данных

👤 Seller (продавец)

python

- id: UUID
- company\_name: str
- inn: str (уникальный)
- kpp: str
- ogrn: str
- legal\_address: str
- actual\_address: str
- phone: str
- email: str
- status: str (PENDING/ACTIVE/BLOCKED)
- rating: Decimal
- verified\_at: DateTime
- created\_at: DateTime
- updated\_at: DateTime

📂 Category (категория)

python

- id: int
- name: str
- slug: str (уникальный)
- description: str
- parent\_id: int (ссылка на родителя)
- level: int
- image\_url: str
- is\_active: bool
- sort\_order: int
- created\_at: DateTime
- updated\_at: DateTime

🏷 Product (товар)

python

- id: int
- seller\_id: UUID
- category\_id: int
- title: str
- description: str
- slug: str (уникальный)
- main\_image\_id: int
- meta\_title: str
- meta\_description: str
- meta\_keywords: str
- status: str (DRAFT/PENDING\_MODERATION/ON\_MODERATION/MODERATED/BLOCKED/ARCHIVED)
- moderation\_comment: str
- published\_at: DateTime
- created\_at: DateTime
- updated\_at: DateTime

🎨 SKU (вариант товара)

python

- id: int
- product\_id: int
- seller\_sku: str
- barcode: str
- name: str
- price: int (в копейках)
- compare\_at\_price: int
- quantity: int
- is\_active: bool
- main\_image\_id: int
- created\_at: DateTime
- updated\_at: DateTime

🔧 Characteristic (характеристика)

python

- id: int
- name: str
- slug: str (уникальный)
- type: str (string/integer/float/boolean)
- is\_global: bool
- created\_at: DateTime
- updated\_at: DateTime

📄 Invoice (накладная)

python

- id: int
- seller\_id: UUID
- invoice\_number: str
- status: str (CREATED/ACCEPTED/REJECTED/CANCELLED)
- warehouse\_id: int
- received\_at: DateTime
- created\_at: DateTime
- updated\_at: DateTime

📊 ProductStatusHistory (история статусов)

python

- id: int
- product\_id: int
- old\_status: str
- new\_status: str
- changed\_by: UUID
- reason: str
- comment: str
- created\_at: DateTime

🔗 Связи между таблицами

text

sellers ─┬── products ──── skus ──── reservations

│       │          │

│       │          └─── sku\_characteristics

│       │

│       └─── product\_images

│            product\_characteristics

│

└─── invoices ──── invoice\_items

categories ─── products

│

└─── category\_characteristics ─── characteristics ─── characteristic\_values

🛠 Инфраструктура

🐳 Docker контейнеры

yaml

- postgres:15 (БД)
- pgadmin (админка PostgreSQL)
- b2b-service (FastAPI приложение)

🔧 Зависимости (requirements.txt)

txt

fastapi==0.104.1

uvicorn[standard]==0.24.0

sqlalchemy==2.0.23

alembic==1.12.1

psycopg2-binary==2.9.9

pydantic==2.5.0

pydantic-settings==2.1.0

python-dotenv==1.0.0

httpx==0.25.1

pytest==7.4.3

pytest-asyncio==0.21.1

📊 Текущий статус

Компонент	Статус	Примечание

Структура проекта	✅ Готово	Полная структура папок

Модели данных	✅ Готово	8 моделей + связи

Docker/PostgreSQL	✅ Работает	Контейнер запущен

Alembic	⚠️ В процессе	Проблемы с кодировкой

API endpoints	❌ Не начато	-

Schemas (Pydantic)	❌ Не начато	-

Тесты	❌ Не начато	-

🚀 Как запустить проект

1️⃣ Активировать виртуальное окружение

bash

venv\Scripts\activate

2️⃣ Запустить PostgreSQL

bash

docker-compose up -d postgres

3️⃣ Проверить подключение к БД

bash

python test\_connection.py

4️⃣ Создать миграции (когда заработает)

bash

alembic revision --autogenerate -m "init models"

5️⃣ Применить миграции

bash

alembic upgrade head

6️⃣ Запустить сервер

bash

uvicorn app.main:app --reload

📌 API Endpoints (план)

Товары

text

POST   /api/v1/products     # Создать товар

GET    /api/v1/products/{id} # Получить товар

PUT    /api/v1/products/{id} # Обновить товар

DELETE /api/v1/products/{id} # Удалить товар

SKU

text

POST   /api/v1/skus          # Создать SKU

PUT    /api/v1/skus/{id}     # Обновить SKU

DELETE /api/v1/skus/{id}     # Удалить SKU

Категории

text

GET    /api/v1/categories          # Список категорий

GET    /api/v1/categories/tree     # Дерево категорий

POST   /api/v1/categories          # Создать категорию

Накладные

text

POST   /api/v1/invoices        # Создать накладную

POST   /api/v1/invoices/accept # Принять накладную

GET    /api/v1/invoices        # Список накладных

⚠️ Известные проблемы

Проблема с кодировкой в Windows

При запуске Alembig возникает ошибка:

text

UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc2 in position 67

Решение в процессе:

Использование параметров подключения вместо строки DSN

Смена кодировки терминала (chcp 65001)

Настройка переменных окружения Python

📈 Следующие шаги

✅ Создать структуру проекта

✅ Написать модели данных

✅ Настроить Docker и БД

⬜ Исправить проблему с Alembic

⬜ Создать Pydantic схемы

⬜ Написать API endpoints

⬜ Добавить тесты

⬜ Интеграция с Auth сервисом

⬜ Интеграция с Moderation сервисом

👥 Команда

Разработчик: Настя

Проект: NeoMarket

Дата: 13.03.2026

Документ создан в рамках разработки маркетплейса NeoMarket
