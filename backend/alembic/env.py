from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base

config = context.config
settings = get_settings()
configured_database_url = config.get_main_option("sqlalchemy.url")
env_database_url = os.getenv("DATABASE_URL")
path_override_requested = os.getenv("TRISHUL_DB_PATH") or os.getenv("TRISHUL_DATA_DIR")
database_url = (
    env_database_url
    or (settings.database_url if path_override_requested else None)
    or configured_database_url
    or settings.database_url
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
