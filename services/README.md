# NeoMarket

Маркетплейс товаров с микросервисной архитектурой.



## Структура проекта
```
neomarket/
├── services/                     # Микросервисы
│   ├── b2b/                      # B2B - Кабинет продавца
│   │   ├── app/                  # Код сервиса
│   │   ├── migrations/           # Миграции БД
│   │   ├── tests/                # Тесты
│   │   ├── Dockerfile            # Для Docker-сборки
│   │   ├── requirements.txt      # Зависимости
│   │   └── README.md             # Документация сервиса
│   │
│   ├── b2c/                       # B2C - Витрина (скоро)
│   ├── moderation/                # Moderation (скоро)
│   └── auth/                      # Auth (скоро)
│
├── infrastructure/                # Общая инфраструктура
│   ├── nginx/                     # 
│   └── scripts/                   # 
│
├── docker-compose.yml              # Запуск всех сервисов
├── .gitignore                      # Игнорируемые файлы
└── README.md                       # Этот файл
```



## Структура микросервиса (шаблон)
```
service-name/
├── app/
│   ├── api/           # Эндпоинты
│   ├── models/        # Модели БД
│   ├── schemas/       # Pydantic схемы
│   └── core/          # Общие утилиты
├── migrations/        # Миграции БД
├── tests/             # Тесты
├── Dockerfile         # Docker образ
├── docker-compose.yml # Локальный запуск
├── requirements.txt   # Зависимости
└── README.md          # Документация сервиса
```

