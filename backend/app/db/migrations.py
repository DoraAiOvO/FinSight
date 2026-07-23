"""Safe Alembic migration entry point for hosted application startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from .session import engine


BACKEND_ROOT = Path(__file__).resolve().parents[2]
POSTGRES_MIGRATION_LOCK_ID = 4_604_733_744_581_681_416


def migration_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def upgrade_database(target_engine: Engine = engine) -> None:
    """Upgrade atomically, serializing concurrent Postgres cold starts."""
    # Alembic receives a connection owned by one engine-level transaction.
    # Successful migrations and the alembic_version update commit together;
    # failures roll back together. A transaction-scoped advisory lock is
    # released automatically in either case, including interrupted cold starts.
    with target_engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": POSTGRES_MIGRATION_LOCK_ID},
            )

        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
