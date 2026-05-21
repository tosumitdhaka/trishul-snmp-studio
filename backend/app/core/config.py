from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _resolve_path(value: str | None, *, default: Path, base: Path) -> Path:
    if not value:
        return default
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


class Settings:
    """Runtime settings for the 2.0.0 application."""

    def __init__(self) -> None:
        backend_dir = Path(__file__).resolve().parents[2]
        repo_root = backend_dir.parent

        self.repo_root = repo_root
        self.backend_dir = backend_dir

        self.data_dir = _resolve_path(
            os.getenv("TRISHUL_DATA_DIR"),
            default=backend_dir / "data",
            base=repo_root,
        )
        self.config_dir = self.data_dir / "configs"
        self.log_dir = self.data_dir / "logs"
        self.secrets_file = self.config_dir / "secrets.json"
        self.bundles_dir = _resolve_path(
            os.getenv("TRISHUL_BUNDLES_DIR"),
            default=self.data_dir / "bundles",
            base=repo_root,
        )
        self.bundle_sets_dir = self.bundles_dir / "sets"
        self.bundle_pointer_file = self.bundles_dir / "active_bundle.json"
        self.tsmi_cache_dir = self.bundles_dir / "cache" / "tsmi"
        self.db_path = _resolve_path(
            os.getenv("TRISHUL_DB_PATH"),
            default=self.data_dir / "trishul_v2.sqlite3",
            base=repo_root,
        )
        self.frontend_dist_dir = _resolve_path(
            os.getenv("TRISHUL_FRONTEND_DIST"),
            default=repo_root / "frontend" / "dist",
            base=repo_root,
        )

        self.app_name = os.getenv("APP_NAME", "Trishul SNMP Suite")
        self.app_version = os.getenv("APP_VERSION", "2.0.0")
        self.app_author = os.getenv("APP_AUTHOR", "Sumit Dhaka")
        self.app_description = os.getenv(
            "APP_DESCRIPTION",
            "Bundle-first SNMP lab and operations shell",
        )
        self.session_timeout = int(os.getenv("SESSION_TIMEOUT", "3600"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.bundled_mibs_dir = backend_dir / "mibs_bundled"

        self.database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{self.db_path.as_posix()}",
        )

    def prepare_paths(self) -> None:
        for path in (
            self.data_dir,
            self.config_dir,
            self.log_dir,
            self.bundles_dir,
            self.bundle_sets_dir,
            self.tsmi_cache_dir,
            self.db_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.prepare_paths()
    return settings


def reset_settings_cache() -> None:
    get_settings.cache_clear()
