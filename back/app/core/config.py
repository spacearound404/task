from functools import lru_cache
from pydantic import BaseModel
import os


class Settings(BaseModel):
    app_name: str = "task-back"
    cors_origins: list[str] = ["*"]
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-prod")
    jwt_algorithm: str = "HS256"
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    public_url: str | None = os.getenv("PUBLIC_URL")
    allow_anon: bool = os.getenv("ALLOW_ANON", "1").lower() in {"1", "true", "yes"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

