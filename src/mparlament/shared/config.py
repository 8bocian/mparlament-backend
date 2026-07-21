"""Application settings (pydantic-settings).

Env-prefixed with ``MPARLAMENT_`` and ``.env`` supported. Defaults mirror spec §7 /
CONVENTIONS C14 (port 4000, Vite origin, uploads dir).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MPARLAMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./mparlament.db"

    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    jwt_ttl_hours: int = 10  # spec TTL 10h

    upload_dir: Path = Path("uploads")
    cors_origins: list[str] = ["http://localhost:5173"]

    host: str = "0.0.0.0"
    port: int = 4000


@lru_cache
def get_settings() -> Settings:
    return Settings()
