"""Application configuration loaded from environment variables."""
import os


def normalize_database_url(url: str) -> str:
    """Normalize common hosted-Postgres URLs for SQLAlchemy's psycopg driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def database_url_from_environment() -> str:
    """Resolve local and Vercel Marketplace database variable names."""
    return normalize_database_url(
        os.getenv("FINSIGHT_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or "sqlite:///./finsight.db"
    )


def auto_migrate_database_from_environment(database_url: str) -> bool:
    """Enable Alembic startup migrations explicitly or for hosted Vercel Postgres."""
    configured = os.getenv("FINSIGHT_AUTO_MIGRATE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return os.getenv("VERCEL") == "1" and database_url.startswith("postgresql")


class Settings:
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    AI_MODEL: str = os.getenv("FINSIGHT_AI_MODEL", "claude-sonnet-5")
    ASSISTANT_MODEL: str = os.getenv(
        "FINSIGHT_ASSISTANT_MODEL", "claude-haiku-4-5"
    )
    ASSISTANT_USER_QUOTA: int = int(
        os.getenv("FINSIGHT_ASSISTANT_USER_QUOTA", "40")
    )
    ASSISTANT_IP_QUOTA: int = int(
        os.getenv("FINSIGHT_ASSISTANT_IP_QUOTA", "80")
    )
    ASSISTANT_QUOTA_WINDOW_SECONDS: int = int(
        os.getenv("FINSIGHT_ASSISTANT_QUOTA_WINDOW_SECONDS", "600")
    )
    CORS_ORIGINS: list[str] = os.getenv(
        "FINSIGHT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    CACHE_TTL_SECONDS: int = int(os.getenv("FINSIGHT_CACHE_TTL", "300"))
    SEC_CACHE_TTL_SECONDS: int = int(os.getenv("FINSIGHT_SEC_CACHE_TTL", "21600"))
    SEC_DOCUMENT_CACHE_TTL_SECONDS: int = int(
        os.getenv("FINSIGHT_SEC_DOCUMENT_CACHE_TTL", "86400")
    )
    SEC_HTTP_TIMEOUT_SECONDS: float = float(
        os.getenv("FINSIGHT_SEC_HTTP_TIMEOUT", "20")
    )
    SEC_USER_AGENT: str = os.getenv(
        "FINSIGHT_SEC_USER_AGENT",
        "FinSight DoraAiOvO@users.noreply.github.com",
    )
    DATABASE_URL: str = database_url_from_environment()
    AUTO_MIGRATE_DATABASE: bool = auto_migrate_database_from_environment(DATABASE_URL)


settings = Settings()
