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
    """Upgrade to Alembic head, serializing concurrent Postgres cold starts."""
    with target_engine.connect() as connection:
        postgres = connection.dialect.name == "postgresql"
        if postgres:
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": POSTGRES_MIGRATION_LOCK_ID},
            )
            connection.commit()

        try:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        finally:
            if postgres:
                if connection.in_transaction():
                    connection.rollback()
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": POSTGRES_MIGRATION_LOCK_ID},
                )
                connection.commit()
