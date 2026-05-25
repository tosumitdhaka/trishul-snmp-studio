from __future__ import annotations

from alembic import command
from alembic.config import Config

from app.core.config import get_settings


def build_alembic_config(
    database_url: str | None = None,
    *,
    use_existing_app_logging: bool = True,
) -> Config:
    settings = get_settings()
    config = Config(str(settings.repo_root / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str((settings.backend_dir / "alembic").resolve()),
    )
    config.set_main_option("prepend_sys_path", str(settings.backend_dir.resolve()))
    config.set_main_option("sqlalchemy.url", database_url or settings.database_url)
    config.attributes["use_existing_app_logging"] = use_existing_app_logging
    return config


def upgrade_database(revision: str = "head", *, database_url: str | None = None) -> None:
    command.upgrade(build_alembic_config(database_url), revision)
