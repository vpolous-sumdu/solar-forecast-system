import os
import sys
from logging.config import fileConfig
from dotenv import load_dotenv

from sqlalchemy import engine_from_config, pool
from alembic import context

# Додаємо шлях до backend, щоб Alembic бачив наші модулі app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

config = context.config

# Використовуємо пряме підключення для міграцій DDL або звичайне
direct_db_url = os.getenv("DIRECT_DATABASE_URL") or os.getenv("DATABASE_URL")

if direct_db_url:
    config.set_main_option("sqlalchemy.url", direct_db_url)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Підключаємо метадані наших моделей (Base.metadata)
from app.db.session import Base
from app.models.station import Station
from app.models.weather import WeatherForecast
from app.models.neural_model import NeuralModel
from app.models.generation import GenerationForecast

target_metadata = Base.metadata




def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
