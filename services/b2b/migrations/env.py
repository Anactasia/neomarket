import os
import sys
from dotenv import load_dotenv

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Базовая настройка
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))
sys.path.append(BASE_DIR)

config = context.config
fileConfig(config.config_file_name)

# URL берём из .env
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

# импортируем все модели для автогенерации миграций
from app.models.base import Base
from app.models.seller import Seller
# сюда можно импортировать другие модели по мере добавления

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()