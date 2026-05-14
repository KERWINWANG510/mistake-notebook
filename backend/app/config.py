from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置（环境变量可覆盖）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_secret: str = "change-me-in-production-use-long-random-string"
    app_version: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    upload_dir: Path = Path("./data/uploads")
    cors_origins: str = ""
    access_token_expire_minutes: int = 60 * 24 * 7

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_restricted(self) -> bool:
        """是否启用 CORS 来源白名单（未配置 cors_origins 时不限制）。"""
        return bool(self.cors_origin_list)


@lru_cache
def get_settings() -> Settings:
    return Settings()
