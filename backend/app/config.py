"""Application configuration loaded from environment variables."""
import os


def normalize_database_url(url: str) -> str:
    """Normalize common hosted-Postgres URLs for SQLAlchemy's psycopg driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Settings:
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    AI_MODEL: str = os.getenv("FINSIGHT_AI_MODEL", "claude-sonnet-5")
    CORS_ORIGINS: list[str] = os.getenv(
        "FINSIGHT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    CACHE_TTL_SECONDS: int = int(os.getenv("FINSIGHT_CACHE_TTL", "300"))
    DATABASE_URL: str = normalize_database_url(
        os.getenv("FINSIGHT_DATABASE_URL", "sqlite:///./finsight.db")
    )


settings = Settings()
