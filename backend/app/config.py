"""Application configuration loaded from environment variables."""
import os


class Settings:
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    AI_MODEL: str = os.getenv("FINSIGHT_AI_MODEL", "claude-sonnet-5")
    CORS_ORIGINS: list[str] = os.getenv(
        "FINSIGHT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    CACHE_TTL_SECONDS: int = int(os.getenv("FINSIGHT_CACHE_TTL", "300"))


settings = Settings()
