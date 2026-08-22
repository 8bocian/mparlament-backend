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

    # Origin the app is reachable under once deployed (e.g. https://mparlament.onrender.com).
    # Engine.IO rejects any origin outside the configured list — including a same-origin one —
    # so the deployed host must be part of ``allowed_origins`` for Socket.IO to hand-shake.
    public_origin: str | None = None

    # Directory holding the built React SPA (Vite ``dist``). Mounted at "/" when it exists, so
    # the single-container deployment serves FE and API from one origin. Unset in dev.
    static_dir: Path | None = None

    host: str = "0.0.0.0"
    port: int = 4000

    @property
    def allowed_origins(self) -> list[str]:
        """CORS/Socket.IO origins: the configured list plus ``public_origin``."""
        origins = list(self.cors_origins)
        if self.public_origin:
            origin = self.public_origin.rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
